"""Entry point for Iris."""
import base64
import json
import logging
import cloudpickle
import pickle
import pkgutil

from flask import Flask, request
from google.appengine.api import memcache, taskqueue

from pluginbase import Plugin
from utils import gcp, pubsub, utils

app = Flask(__name__)
plugins = []


def store(key, value, chunksize=950000):
    serialized = cloudpickle.dumps(value, 2)
    values = {}
    for i in xrange(0, len(serialized), chunksize):
        values['%s.%s' % (key, i // chunksize)] = serialized[i:i + chunksize]
    return memcache.set_multi(values)


def retrieve(key):
    result = memcache.get_multi(['%s.%s' % (key, i) for i in xrange(32)])
    serialized = ''.join(
        [v for k, v in sorted(result.items()) if v is not None])
    return pickle.loads(serialized)


def create_app():
    """
    Do initialization
    """
    hostname = utils.get_host_name()
    logging.info("Starting Iris on %s", hostname)
    client = pubsub.get_pubsub_client()
    pubsub.create_topic(client, 'iris_gce')
    pubsub.create_subscriptions(client, 'iris_gce',
                                'iris_gce')
    pubsub.pull(client, 'iris_gce',
                "https://{}/tag_one".format(hostname))
    tags = utils.get_tags()
    on_demand = utils.get_ondemand()
    for _, module, _ in pkgutil.iter_modules(["plugins"]):
        __import__('plugins' + '.' + module)
    for plugin in Plugin.plugins:
        plugin.set_on_demand(on_demand)
        plugin.set_tags(tags)


create_app()


@app.route('/')
def index():
    """
    Main Page
    :return:
    """
    return 'this aren\'t the droids you\'re looking for', 200


@app.route('/tag_one', methods=['POST'])
def tag_one():
    data = json.loads(base64.b64decode(request.json['message']['data']))
    logging.info(data)
    try:
        method_name = data['protoPayload']['methodName']
        for plugin in Plugin.plugins:
            if plugin.is_on_demand():
                for method in plugin.methodsNames():
                    if method.lower() in method_name.lower():
                        gcp_object = plugin.get_gcp_object(data)
                        if gcp_object is not None:
                            project_id = data['resource']['labels'][
                                'project_id']
                            logging.info("Calling tag one for %s", plugin.__class__.__name__)
                            plugin.tag_one(gcp_object, project_id)
                            plugin.do_batch()
    except Exception as e:
        logging.error(e)
    return 'ok', 200


@app.route('/tasks/schedule', methods=['GET'])
def schedule():
    """
    Checks if it's time to run a schedule.
    Returns:
    """
    logging.info("Nothing here")
    projects = gcp.get_all_projetcs()
    for project in sorted(projects, key=lambda x: x['name']):
        project_id = str(project['projectId'])
        service_list = gcp.list_services(project_id)
        logging.debug("Creating deferred task for %s", project_id)
        for plugin in Plugin.plugins:
            if utils.is_service_enbaled(service_list, plugin.api_name()):
                store(plugin.__class__.__name__, plugin)
                task = taskqueue.add(queue_name='iris-tasks',
                                     url="/tasks/do_tag",
                                     method='GET',
                                     params={
                                         'project_id': project_id,
                                         'plugin': plugin.__class__.__name__,
                                     })
                logging.debug('Task %s for %s enqueued, ETA %s.', task.name,
                              plugin.__class__.__name__, task.eta)
            else:
                logging.debug("Service %s is not enabled", plugin.api_name())
    return 'ok', 200


@app.route('/tasks/do_tag', methods=['GET'])
def do_tag():
    f = retrieve(request.args['plugin'])
    project_id = request.args['project_id']
    f.do_tag(project_id)
    return 'ok', 200


if __name__ == "__main__":
    # TODO debug = False
    app.run(debug=True)
