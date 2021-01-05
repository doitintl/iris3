"""Entry point for Iris."""
import base64
import json
import logging
import os
import pkgutil
import typing

import flask

from pluginbase import Plugin
from util import pubsub_utils, conf_utils, gcp_utils, utils
from util.utils import cls_by_name

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

app = flask.Flask(__name__)


def __init_flaskapp():
    logging.info('Starting Iris')

    def create_subscriptions():
        pubsub_utils.create_subscriptions('do_label', pubsub_utils.scheduled_labeling_topic())
        pubsub_utils.create_subscriptions('label_one', pubsub_utils.logs_topic())

    def load_plugins():
        on_demand: typing.List[str] = conf_utils.get_ondemand()
        for _, module, _ in pkgutil.iter_modules(['plugins']):
            module_name = 'plugins' + '.' + module
            __import__(module_name)
            plugin_class = utils.cls_by_name(module_name + '.' + module.title())
            Plugin.plugins.append(plugin_class)
            plugin_class.set_on_demand(on_demand)

    create_subscriptions()
    load_plugins()


__init_flaskapp()


@app.route('/')
def index():
    return "These aren't the droids you are looking for", 200


@app.route('/schedule', methods=['GET'])
def schedule():
    """
    Checks if it'fully_qualified_classname time to run a schedule.
    When it is, send out a task per plugin  to tag all objects.
    Returns:
    """
    logging.info('schedule, headers %s', sorted(dict(flask.request.headers)))
    projects = gcp_utils.get_all_projects()
    for project_id in sorted(projects):
        for plugin in Plugin.plugins:
            msg_dict = {'project_id', project_id,
                        'plugin', plugin.__class__.__name__
                        }
            msg = json.dumps(msg_dict)
            pubsub_utils.publish(project_id=project_id, msg=msg, topic_id=pubsub_utils.scheduled_labeling_topic())
            logging.info('Task for project %s and plugin  %s enqueued',
                         project_id, plugin.__class__.__name__)
    return 'ok', 200


# Pubsub push endpoint
@app.route('/label_one', methods=['POST'])
def label_one():
    """Receive logging-object about a new GCP object (from PubSub from a logging
    sink), and label it."""
    envelope = flask.request.get_json()
    if not envelope:
        msg = 'no Pub/Sub message received'
        logging.error(f'Error: {msg}')
        return f'Bad Request: {msg}', 400

    if not isinstance(envelope, dict) or "message" not in envelope:
        msg = 'invalid Pub/Sub message format'
        logging.error(f"Error: {msg}")
        return f'Bad Request: {msg}', 400

    pubsub_message = envelope["message"]

    data = json.loads(base64.b64decode(pubsub_message['data']))
    __label_one_from_logline(data)
    return 'ok', 200


# For testing
@app.route('/label_one_from_logline', methods=['POST'])
def label_one_from_logline():
    data: str = flask.request.json
    __label_one_from_logline(data)
    return 'ok', 200


def __label_one_from_logline(data):
    supported_method = data['protoPayload']['methodName']
    for plugin_cls in Plugin.plugins:
        if plugin_cls.is_on_demand():
            plugin = plugin_cls()
            for method_from_log in plugin.method_names():
                if method_from_log.lower() in supported_method.lower():
                    gcp_object = plugin.get_gcp_object(data)
                    if gcp_object is not None:
                        project_id = data['resource']['labels']['project_id']
                        logging.info("Calling label_one for %s ", plugin.__class__.__name__)
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
    logging.info("Will use plugin %s", plugin_name)
    cls = cls_by_name('plugins' + '.' + plugin_name.lower() + '.' + plugin_name)
    plugin = cls()
    project_id = args.pop('project_id')
    plugin.do_label(project_id, **args)
    return 'ok', 200


if __name__ in ['__main__']:
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    port = os.environ.get('PORT', '8080')
    port = int(port)
    app.run(host="127.0.0.1", port=port, debug=True)
