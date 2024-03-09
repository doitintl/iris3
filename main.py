"""Entry point for Iris."""

import sys

print("Initializing ", file=sys.stderr)
from util.utils import init_logging, sort_dict

# Must init logging before any library code writes logs (which would then just override our config)
init_logging()

import flask
from flask import Response
from google.auth.transport import requests
from google.oauth2 import id_token
from util.gcp.gcp_utils import (
    increment_invocation_count,
    count_invocations_by_path,
    get_project,
    current_project_id,
)
from util.gcp.detect_gae import detect_gae

app = flask.Flask(__name__)
if detect_gae():
    import google.appengine.api

    app.wsgi_app = google.appengine.api.wrap_wsgi_app(app.wsgi_app)

from functools import lru_cache

from typing import Dict, Type, List

import time

cold_start_begin = time.time()
import base64
import json
import logging
import os

from plugin import Plugin, PluginHolder
from util import pubsub_utils, utils, config_utils
from util.gcp import gcp_utils
from util.gcp.gcp_utils import (
    detect_gae,
    is_appscript_project,
    all_projects,
    gae_memory_logging,
    enable_cloudprofiler,
)

from util.config_utils import (
    is_project_enabled,
    iris_homepage_text,
)
from util.utils import log_time, timing

ENABLE_PROFILER = False

# Profiler initialization. It starts a daemon thread which continuously collects and uploads profiles.
if detect_gae() and ENABLE_PROFILER:
    enable_cloudprofiler()
else:
    logging.info("Cloud Profiler not in use")

gcp_utils.set_env()

logging.info("env  is %s", sort_dict((os.environ.copy())))
logging.info(
    "Configuration is %s", json.dumps(config_utils.get_config()).replace("\n", "")
)

PluginHolder.init()


@app.route("/")
def index():
    increment_invocation_count("index")
    with gae_memory_logging("index"):
        msg = iris_homepage_text()

        logging.info(
            "index(); invocations of GAE instance : %s", count_invocations_by_path()
        )
        return Response(msg, mimetype="text/plain", status=200)


@app.route("/_ah/warmup")
def warmup():
    increment_invocation_count("warmup")
    with gae_memory_logging("warmup"):
        logging.info("warmup() called")

    return "", 200, {}


@app.route("/label_all", methods=["POST"])
@log_time
def label_all():
    with gae_memory_logging("label_all"):
        logging.info("Start label_all() invocation")
        increment_invocation_count("label_all")
        __check_pubsub_jwt()
        return __label_multiple_types(True)


@app.route("/schedule", methods=["GET"])
@log_time
def schedule():
    with gae_memory_logging("schedule"):
        logging.info("Start schedule() invocation")
        increment_invocation_count("schedule")
        # Not validated with JWT because validated with cron header
        is_cron = flask.request.headers.get("X-Appengine-Cron")
        if not is_cron:
            return "Access Denied: No Cron header found", 403
        label_all_types = config_utils.label_all_on_cron()
        return __label_multiple_types(label_all_types)


def __label_multiple_types(label_all_types: bool):
    """
    Send out a message per-plugin per-project; each msg labels objects of a given type and project.
    :param label_all_types: if false, only label those that are
    not labeled on creation (CloudSQL) or those that must be relabeled on cron (Disks),
    but if true, label all types;
    """
    assert label_all_types is not None
    try:
        enabled_projects = __get_enabled_projects()
        __send_pubsub_per_projectplugin(
            enabled_projects, label_all_types=label_all_types
        )
        # All errors are actually caught, logged and ignored *before* this point,
        # since most errors are unrecoverable.
        return "OK", 200
    except Exception:
        logging.exception("In schedule()")
        return "Error", 500


@lru_cache(maxsize=1)
def __get_enabled_projects() -> List:
    configured_as_enabled = config_utils.enabled_projects()
    if configured_as_enabled:
        enabled_projs = configured_as_enabled
    else:
        all_proj = all_projects()

        # In some cases, lots of appscript projects would appear.
        # so here we filter them out. However, In my testing, we do NOT get appscript projects in the list.
        nonappscript_projects = (p for p in all_proj if not is_appscript_project(p))
        # The following filtering probably does nothing since the else-clause that
        # that we are in is reached only if there are no explicitly enabled projects.
        enabled_only = (
            p for p in nonappscript_projects if config_utils.is_project_enabled(p)
        )
        enabled_projs = list(enabled_only)

    enabled_projs.sort()
    if not enabled_projs:
        raise Exception("No projects enabled at all")

    return enabled_projs


def __send_pubsub_per_projectplugin(configured_projects: List, label_all_types: bool):
    msg_count = 0
    for project_id in configured_projects:
        for plugin_cls in PluginHolder.plugins:

            if (
                not plugin_cls.is_labeled_on_creation()
                or plugin_cls.relabel_on_cron()
                or label_all_types
            ):
                pubsub_utils.publish(
                    msg=json.dumps(
                        {"project_id": project_id, "plugin": plugin_cls.__name__}
                    ),
                    topic_id=pubsub_utils.schedulelabeling_topic(),
                )

                logging.info(
                    "Sent do_label message for %s , %s",
                    project_id,
                    plugin_cls.__name__,
                )
            msg_count += 1
    logging.info(
        "schedule() sent %d messages to label %d projects",
        msg_count,
        len(configured_projects),
    )


@app.route("/label_one", methods=["POST"])
def label_one():
    """Message received from PubSub when the log sink detects a new resource"""
    logging.info("label_one called")
    increment_invocation_count("label_one")
    ok = __check_pubsub_jwt()
    if not ok:
        return "JWT Failed", 400

    with gae_memory_logging("label_one"):

        plugins_found = []
        data = {}
        try:
            """
            PubSub push endpoint for messages from the Log Sink
            """
            # Performance question: There are multiple log lines for each object-creation, for example,
            # one for request and one for response. So, we may be labeling each object multiple times,
            # which is a waste of resources.
            #
            # Or maybe not. Maybe the first PubSub-triggered action fails, because the resource is not initialized, and
            # then the second one succeeds; need to check that.

            data = __extract_pubsub_content()

            method_from_log = data["protoPayload"]["methodName"]
            for plugin_cls in PluginHolder.plugins.keys():
                method_names = plugin_cls.method_names()

                for supported_method in method_names:
                    if supported_method.lower() in method_from_log.lower():
                        if plugin_cls.is_labeled_on_creation():
                            logging.info(
                                "plugin_cls %s, with method %s",
                                plugin_cls.__name__,
                                method_from_log,
                            )
                            __label_one_0(data, plugin_cls)

                        plugins_found.append(
                            plugin_cls.__name__
                        )  # Append it even if not used due to is_labeled_on_creation False

            if not plugins_found:
                logging.info(
                    "(This message does not indicate an error if the plugin is disabled.)"
                    + " No plugins found for %s. Enabled plugins are %s",
                    method_from_log,
                    config_utils.enabled_plugins(),
                )

            if len(plugins_found) > 1:
                raise Exception(
                    "Error: Multiple plugins found %s for %s"
                    % (plugins_found, method_from_log)
                )
            logging.info("OK for label_one %s", method_from_log)
            # All errors are actually caught before this point,
            # since most errors are unrecoverable.
            return "OK", 200
        except Exception:
            project_id = data.get("resource", {}).get("labels", {}).get("project_id")
            logging.exception("Error on label_one %s %s", plugins_found, project_id)
            return "Error", 500


def __check_pubsub_jwt():
    try:
        # TODO the sample https://github.com/GoogleCloudPlatform/python-docs-samples/blob/ff4c1d55bb5b6995c63383469535604002dc9ba2/appengine/standard_python3/pubsub/main.py#L69
        # has this. I am not sure why or how the token arg gets there.
        # if request.args.get("token", "") != current_app.config["PUBSUB_VERIFICATION_TOKEN"]:
        #     return "Invalid request", 400
        bearer_token = flask.request.headers.get("Authorization")
        token = bearer_token.split(" ")[1]

        claim = id_token.verify_oauth2_token(token, requests.Request())

        # example claim:  { "aud": "https://iris3-dot-myproj.appspot.com/label_one?token=xxxxxxxxx",
        #     "azp": "1125239305332910191520",
        #     "email": "iris-msg-sender@myproj.iam.gserviceaccount.com",
        #     "email_verified": True, "exp": 1708281691, "iat": 1708278091,
        #     "iss": "https://accounts.google.com", "sub": "1125239305332910191520"}

        if not (is_email_verif := claim.get("email_verified")):
            logging.error(f"Email verified was {is_email_verif}")
            return False

        # logging.info("Claims: " + str(claim))
        if (
            email := claim.get("email")
        ) != f"iris-msg-sender@{current_project_id()}.iam.gserviceaccount.com":
            logging.error("incorrect email in JWT " + email)
            return False
    except Exception as e:
        logging.exception(f"Invalid JWT token: {e}")
        return False
    # logging.info("JWT Passed")

    return True


def __label_one_0(data, plugin_cls: Type[Plugin]):
    plugin = PluginHolder.get_plugin_instance(plugin_cls)
    gcp_object = plugin.get_gcp_object(data)
    if gcp_object is not None:
        project_id = data["resource"]["labels"]["project_id"]

        if is_project_enabled(project_id):
            logging.info(
                # Bug: the below resource-name is INCORRECT in case of CreateSubscription, where the topic name is returned but it is only a log line
                "Will label_one(): %s ",
                data["protoPayload"]["resourceName"],
            )
            plugin.label_resource(gcp_object, project_id)
            plugin.do_batch()
        else:
            msg = (
                f"Skipping label_one({plugin_cls.__name__}) in unsupported "
                f"project {project_id}; (Should not get here in current design, since the Sink filter should only include "
                f"supported projects; also, schedule() already filters for the enabled projects. "
                f"However, if the Sink filter was not updated to match config.yaml, or in local development"
                f"if a command is given to label an arbitrary project that is not in config.yaml, this can happen"
            )
            logging.info(msg)
    else:
        logging.error(
            "Cannot find gcp_object to label. (Sometimes still allows labeling, "
            + "e.g. for BQ datasets where serviceData is missing), based on %s",
            utils.shorten(str(data.get("resource")), 300),
        )


def __extract_pubsub_content() -> Dict:
    """Take the value at the relevant key in the logging message from PubSub,
    Base64-decode, convert to Python object."""

    envelope = flask.request.get_json()
    msg = envelope.get("message", {})

    logging.info(
        "PubSub deliveryAttempt %s; messageId %s, timestamp %s",
        envelope.get("deliveryAttempt", "N/A"),
        msg.get("messageId", "N/A"),
        msg.get("publishTime", "N/A"),
    )

    if not envelope:
        raise FlaskException("Expect JSON, was empty")

    data = json.loads(base64.b64decode(envelope["message"]["data"]))
    return data


@app.route("/do_label", methods=["POST"])
def do_label():
    """Receives a push message from PubSub, sent from schedule() above,
    and labels all objects of a given plugin and project_id.
    """
    increment_invocation_count("do_label")
    logging.info("do_label called")
    ok = __check_pubsub_jwt()
    if not ok:
        return "JWT Failed", 400

    with gae_memory_logging("do_label"):

        project_id = ""  # set up variables to allow logging in Exception block at end
        plugin_class_name = ""
        try:
            data = __extract_pubsub_content()
            plugin_class_name = data["plugin"]

            plugin = PluginHolder.get_plugin_instance_by_name(plugin_class_name)
            if not plugin:
                logging.info(
                    "(OK if plugin is disabled.) No plugins found for %s. Enabled plugins are %s",
                    plugin_class_name,
                    config_utils.enabled_plugins(),
                )
            else:
                project_id = data["project_id"]
                with timing(f"do_label {plugin_class_name} {project_id}"):
                    logging.info(
                        "do_label() for %s in %s",
                        plugin.__class__.__name__,
                        project_id,
                    )
                    plugin.label_all(project_id)
                logging.info("OK on do_label %s %s", plugin_class_name, project_id)
            # All errors are actually caught before this point, since most errors are unrecoverable.
            # However, Subscription gets "InternalServerError"" "InactiveRpcError" on occasion
            #  so retry could be relevant. B

            return "OK", 200
        except Exception:
            logging.exception("Error on do_label %s %s", plugin_class_name, project_id)
            return "Error", 500


class FlaskException(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv["message"] = self.message
        return rv


@app.errorhandler(FlaskException)
def handle_invalid_usage(error):
    logging.exception("")
    response = flask.jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


logging.info(f"Coldstart took {int((time.time() - cold_start_begin) * 1000)} ms")

if __name__ in ["__main__"]:
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    port = os.environ.get("PORT", 8000)
    logging.info("Running __main__ for main.py, port %s", port)
    app.run(host="127.0.0.1", port=port, debug=True)
