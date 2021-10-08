"""Entry point for Iris."""
import base64
import json
import logging
import os
import typing

import flask

import util.gcp_utils
from plugin import Plugin
from util import pubsub_utils, gcp_utils, utils
from util.gcp_utils import detect_gae

from util.config_utils import iris_prefix, is_project_included
from util.utils import init_logging, truncate_mid

import googlecloudprofiler

# Must init logging before any library code writes logs (which would overwide our config)

init_logging()

# Profiler initialization. It starts a daemon thread which continuously collects and uploads profiles.
if detect_gae():
    try:
        googlecloudprofiler.start(verbose=3)
    except (ValueError, NotImplementedError) as exc:
        msg = (
            ". This is not needed in local development, unless you want to experiment with the cloud debugger"
            if "Service name must be provided" in str(exc)
            else ""
        )

    print("Exception initializing the Cloud Profiler", exc, msg)  #


logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)
logging.info("logging: Initialized logger")

gcp_utils.set_env()

app = flask.Flask(__name__)


def __init_plugins():
    Plugin.init()
    logging.info("Initialized Iris Plugins in process %s", os.getpid())


__init_plugins()


@app.route("/")
def index():
    msg = f"I'm {iris_prefix().capitalize()}, pleased to meet you!"
    logging.info(msg)
    return msg, 200


@app.route("/schedule", methods=["GET"])
def schedule():
    """
    Send out a message per-plugin per-project to label all objects of that type and project.
    """
    is_cron = flask.request.headers.get("X-Appengine-Cron")
    if not is_cron:
         return "Access Denied: No Cron header found", 403

    skipped_projects = list(
        filter(lambda p: not is_project_included(p), gcp_utils.all_projects())
    )
    if skipped_projects:
        logging.info("schedule() not processing: %s", skipped_projects)
    included_projects = gcp_utils.all_included_projects()
    logging.info(
        "schedule() processing %d projects: %s",
        len(included_projects),
        ", ".join(included_projects),
    )
    msg_count = 0
    for project_id in included_projects:
        for plugin_cls in Plugin.subclasses:
            pubsub_utils.publish(
                msg=json.dumps(
                    {"project_id": project_id, "plugin": plugin_cls.__name__}
                ),
                topic_id=pubsub_utils.schedulelabeling_topic(),
            )
            msg_count += 1
    logging.info(
        "schedule() send messages to label %d projects, %d messages",
        len(included_projects),
        msg_count,
    )
    return "OK", 200

g
@app.route("/label_one", methods=["POST"])
def label_one():
    try:
        """
        PubSub push endpoint for messages from the Log Sink
        """
        # Performance question: There are multiple messages for each object-creation, for example
        # one for request and one for response. So, we may be labeling each object multiple times,
        # which is a waste of resources.
        #
        # Or maybe the first PubSub-triggered action fails, because the resource is not initialized, and
        # then the second one succeeds; need to check that.

        data = __extract_pubsub_content()

        method_from_log = data["protoPayload"]["methodName"]

        for plugin_cls in Plugin.subclasses:
            if plugin_cls.is_labeled_on_creation():
                plugin = plugin_cls()
                for supported_method in plugin.method_names():
                    if supported_method.lower() in method_from_log.lower():
                        __label_one_0(data, plugin)

        return "OK", 200
    except Exception as e:
        # Return 200 so that PubSub doesn't keep trying indefinitely
        logging.exception(f"In label_one(): {e}")
        return "OK", 200


def __label_one_0(data, plugin):
    gcp_object = plugin.get_gcp_object(data)
    if gcp_object is not None:
        project_id = data["resource"]["labels"]["project_id"]
        if is_project_included(project_id):
            logging.info("Will label_one() in %s, %s", project_id, gcp_object)
            plugin.label_one(gcp_object, project_id)
            plugin.do_batch()
        else:
            msg = (
                f"Skipping label_one({plugin.__class__.__name__}) in unsupported "
                f"project ${project_id}; (Should not get here in current design, since the Sink filter should only include "
                f"supported projects). However, if the Sink filter was not updated to match config.yaml, or in local development"
                f"if a command is given to label an arbirary project that is not in config.yaml, this can happen"
            )
            logging.info(msg)
    else:
        logging.error(
            "Cannot find gcp_object to label based on %s",
            utils.shorten(str(data.get("resource")), 300),
        )


def __extract_pubsub_content() -> typing.Dict:
    """Take the value at the relevant key in the logging message from PubSub,
    Base64-decode, convert to Python object."""
    __check_pubsub_verification_token()

    envelope = flask.request.get_json()
    if not envelope:
        raise FlaskException("Expect JSON")

    data = json.loads(base64.b64decode(envelope["message"]["data"]))
    return data


@app.route("/do_label", methods=["POST"])
def do_label():

    try:
        """Receive a push message from PubSub, sent from schedule() above,
        with instructions to label all objects of a given plugin and project_id.
        """
        data = __extract_pubsub_content()

        plugin_class_name = data["plugin"]
        plugin = Plugin.create_plugin(plugin_class_name)
        project_id = data["project_id"]
        logging.info("do_label() for %s in %s", plugin.__class__.__name__, project_id)
        plugin.do_label(project_id)
        return "OK", 200
    except Exception as e:
        # Return 200 so that PubSub doesn't keep trying indefinitely
        logging.exception(f"In do_label(): {e}")
        return "OK", 200


def __check_pubsub_verification_token():
    """Token verifying that only PubSub accesses PubSub push endpoints"""
    known_token = util.gcp_utils.pubsub_token()
    if not known_token:
        raise FlaskException(
            f"Should define expected token in env. Keys were {list(os.environ.keys())}",
            400,
        )

    token_from_args = flask.request.args.get("token", "")
    if known_token != token_from_args:
        raise FlaskException(f'Access denied: Invalid token "{known_token}"', 403)


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
    logging.exception(error)
    response = flask.jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


if __name__ in ["__main__"]:
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    port = os.environ.get("PORT", 8000)
    logging.info("Running __main__ for main.py, port %s", port)
    app.run(host="127.0.0.1", port=port, debug=True)
