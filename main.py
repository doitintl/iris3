"""Entry point for Iris."""
import base64
import json
import logging
import os
import pkgutil
import typing

import flask

from pluginbase import Plugin
from util import pubsub_utils, config_utils, gcp_utils, utils
from util.utils import cls_by_name

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

gcp_utils.set_project_env_if_needed()

app = flask.Flask(__name__)

PLUGINS_MODULE = 'plugins'


def __init_flaskapp():
    logging.info('Starting Iris in process %s', os.getpid())

    def create_subscriptions():
        pubsub_utils.create_subscription('do_label', pubsub_utils.request_full_labeling_topic())
        pubsub_utils.create_subscription('label_one', pubsub_utils.logs_topic())

    def load_plugins():
        on_demand: typing.List[str] = config_utils.get_ondemand()
        for _, module, _ in pkgutil.iter_modules([PLUGINS_MODULE]):
            module_name = PLUGINS_MODULE + '.' + module
            __import__(module_name)
            plugin_class = utils.cls_by_name(module_name + '.' + module.title())
            Plugin.plugin_classes.append(plugin_class)
            plugin_class.set_on_demand(on_demand)


        assert Plugin.plugin_classes, 'No plugins defined'

    create_subscriptions()
    load_plugins()


__init_flaskapp()


@app.route('/')
def index():
    return "These aren't the droids you are looking for", 200


@app.route('/schedule', methods=['GET'])
def schedule():
    """
    Send out a message per-plugin per-project to label all objects of that type and project.
    """
    logging.info('In schedule(), headers are %s', dict(flask.request.headers))
    projects = gcp_utils.get_all_projects()
    for project_id in projects:
        for plugin_cls in Plugin.plugin_classes:
            msg_dict = {'project_id': project_id,
                        'plugin': plugin_cls.__name__}
            msg = json.dumps(msg_dict)
            pubsub_utils.publish(msg=msg, topic_id=pubsub_utils.request_full_labeling_topic())

    return 'ok', 200


# Pubsub push endpoint
@app.route('/label_one', methods=['POST'])
def label_one():
    """Receive logging-object about a new GCP object (from PubSub
    from a logging sink), and label it."""

    envelope = flask.request.get_json()
    if not envelope:
        raise ValueError('Expect JSON')
    b64encoded_json: str = envelope['message']['data']
    data: typing.Dict = json.loads(base64.b64decode(b64encoded_json))
    __label_one_from_logline(data)
    return 'ok', 200


def __label_one_from_logline(data: typing.Dict):
    method_from_logline = data['protoPayload']['methodName']
    for plugin_cls in Plugin.plugin_classes:
        if plugin_cls.is_on_demand():
            plugin = plugin_cls()
            for supported_method in plugin.method_names():
                if supported_method.lower() in method_from_logline.lower():
                    gcp_object = plugin.get_gcp_object(data)
                    if gcp_object is not None:
                        project_id = data['resource']['labels']['project_id']
                        logging.info("Calling label_one() for %s in %s ", plugin.__class__.__name__, project_id)
                        plugin.label_one(gcp_object, project_id)
                        plugin.do_batch()


@app.route('/do_label', methods=['GET', 'POST'])
def do_label():
    """
    :param (in HTTP request) is
    'plugin' with plugin short-classname and
    'project_id' with project id.
    """
    logging.info('do_label, headers %s', sorted(dict(flask.request.headers)))
    args = dict(flask.request.args)
    plugin_name = args.pop('plugin')
    cls = cls_by_name(PLUGINS_MODULE + '.' + plugin_name.lower() + '.' + plugin_name)
    plugin = cls()
    project_id = args.pop('project_id')
    logging.info("do_label() for %s in %s", plugin_name, project_id)
    plugin.do_label(project_id, **args)
    return 'ok', 200


if __name__ in ['__main__']:
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    port = os.environ.get('PORT', '5000')
    port = int(port)
    app.run(host="127.0.0.1", port=port, debug=True)
