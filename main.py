"""Entry point for Iris."""
import base64
import json
import logging
import pickle
import pkgutil

from flask import Flask, request
from google.appengine.api import memcache, taskqueue

from pluginbase import Plugin
from utils import gcp, pubsub, utils

app = Flask(__name__)
plugins = []


def store(key, value, chunksize=950000):
    serialized = pickle.dumps(value, 2)
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
    pubsub.create_subscriptions(client, 'iris_preemptible_subscription',
                                'iris_preemptible_topic')
    pubsub.pull(client, 'iris_preemptible_subscription',
                "https://iris-dot-{}/tag_preemptible".format(hostname))

    for _, module, _ in pkgutil.iter_modules(["plugins"]):
        __import__('plugins' + '.' + module)


create_app()


@app.route('/')
def index():
    """
    Main Page
    :return:
    """

    return 'this aren\'t the droids you\'re looking for', 200


@app.route('/tag_preemptible', methods=['POST'])
def tag_preemptible():
    data = json.loads(base64.b64decode(request.json['message']['data']))
    logging.info(data)
    logging.info(data['resource']['labels']['project_id'])
    logging.info(data['resource']['labels']['zone'])
    logging.info(data['protoPayload']['request']['name'])

    return 'ok', 200


@app.route('/tasks/schedule', methods=['GET'])
def schedule():
    """
    Checks if it's time to run a schedule.
    Returns:
    """
    return 'ok', 200
    logging.debug("From Cron start /tasks/schedule")
    projects = gcp.get_all_projetcs()
    for project in sorted(projects, key=lambda x: x['name']):
        project_id = str(project['projectId'])
        logging.debug("Creating deferred task for   %s", project_id)
        for plugin in Plugin.plugins:
            store(plugin.__class__.__name__, plugin)
            task = taskqueue.add(queue_name='iris-tasks',
                                 url="/tasks/do_tag",
                                 method='GET',
                                 params={
                                     'project_id': project_id,
                                     'plugin': plugin.__class__.__name__,
                                 })
            logging.debug('Task %s enqueued, ETA %s.', task.name, task.eta)
    return 'ok', 200


@app.route('/tasks/do_tag', methods=['GET'])
def do_tag():
    f = retrieve(request.args['plugin'])
    project_id = request.args['project_id']
    f.do_tag(project_id)
    return 'ok', 200


if __name__ == "__main__":
    app.run(debug=True)
