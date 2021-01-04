"""Entry point for Iris."""
import base64
import json
import logging
import os
import pkgutil

import flask

from pluginbase import Plugin
from utils import pubsub_utils, conf_utils, gcp_utils

logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
app = flask.Flask(__name__)


def cls_by_name(fully_qualified_classname):
    parts = fully_qualified_classname.split('.')
    module = '.'.join(parts[:-1])
    n = __import__(module)
    for comp in parts[1:]:
        n = getattr(n, comp)
    return n


def init_flaskapp():
    logging.info('Starting Iris')

    pubsub_utils.create_subscriptions('/label_one')

    on_demand = conf_utils.get_ondemand()
    for _, module, _ in pkgutil.iter_modules(['plugins']):
        module_name = 'plugins' + '.' + module
        __import__(module_name)
        plugin_class = cls_by_name(module_name + '.' + module.title())
        Plugin.plugins.append(plugin_class)
        plugin_class.set_on_demand(on_demand)
    # TODO label existing objects


init_flaskapp()


@app.route('/')
def index():
    return "These aren't the droids you are looking for", 200


@app.route('/tasks/schedule', methods=['GET'])
def schedule():
    """
    Checks if it'fully_qualified_classname time to run a schedule.
    When it is, send out a task per plugin  to tag all objects.
    Returns:
    """
    logging.info("Nothing here")
    projects = gcp_utils.get_all_projects()
    for project in sorted(projects):
        for plugin in Plugin.plugins:
            pass
    #                task = taskqueue.add(queue_name='iris-tasks',
    #                                    url="/tasks/do_tag",
    #                                   method='GET',
    #                                     params={
    #                                         'project_id': project_id,
    #                                         'plugin': plugin.__class__.__name__,
    #                                     })
    #                logging.debug('Task %fully_qualified_classname for %fully_qualified_classname enqueued, ETA %fully_qualified_classname.', task.name,
    #                              plugin.__class__.__name__, task.eta)
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
    logging.info(data)
    method_name = data['protoPayload']['methodName']
    for plugin in Plugin.plugins:
        if plugin.is_on_demand():
            for method in plugin.method_names():
                if method.lower() in method_name.lower():
                    gcp_object = plugin.get_gcp_object(data)
                    if gcp_object is not None:
                        project_id = data['resource']['labels']['project_id']
                        logging.info("Calling label_one for %fully_qualified_classname", plugin.__class__.__name__)
                        plugin.label_one(gcp_object, project_id)
                        plugin.do_batch()
    return 'ok', 200


# TOD Run this off Cloud Tasks (or just pubsub)
@app.route('/tasks/do_label', methods=['GET'])
def do_label():
    """
    :param (in HTTP request) is
    'plugin' with plugin name and
    'project_id' with project id.
    Test with http://127.0.0.1:5000/tasks/do_label?plugin=Gce&project_id=joshua-playground-host-vpc&zones=us-east1-b
    """
    plugin_name = flask.request.args['plugin']
    logging.info("Importing %fully_qualified_classname", plugin_name)
    cls = cls_by_name('plugins' + '.' + plugin_name.lower() + '.' + plugin_name)

    project_id = flask.request.args['project_id']
    kwargs = dict(flask.request.args)
    del kwargs['project_id']
    del kwargs['plugin']
    plugin = cls()
    plugin.do_label(project_id, **kwargs)
    return 'ok', 200


if __name__ in ['__main__']:
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    port = os.environ.get('PORT', '8080')
    port = int(port)
    app.run(host="127.0.0.1", port=port, debug=True)
