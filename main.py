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

    on_demand: typing.List[str] = config_utils.get_ondemand()
    for _, module, _ in pkgutil.iter_modules([PLUGINS_MODULE]):
        module_name = PLUGINS_MODULE + '.' + module
        __import__(module_name)
        plugin_class = utils.cls_by_name(module_name + '.' + module.title())
        Plugin.plugin_classes.append(plugin_class)
        plugin_class.set_on_demand(on_demand)
    assert Plugin.plugin_classes, 'No plugins defined'


__init_flaskapp()


@app.route('/')
def index():
    return "These aren't the droids you are looking for", 200


# TORO return info on the number of tasks that were published
@app.route('/schedule', methods=['GET'])
def schedule():
    """
    Send out a message per-plugin per-project to label all objects of that type and project.
    """
    # logging.info('In schedule(), headers are %s', dict(flask.request.headers))
    is_cron = flask.request.headers.get('X-Appengine-Cron')
    if not is_cron:
        return 'Access Denied: No Cron header found', 403
    projects = gcp_utils.get_all_projects()
    for project_id in projects:
        for plugin_cls in Plugin.plugin_classes:
            msg_dict = {'project_id': project_id,
                        'plugin': plugin_cls.__name__}
            msg = json.dumps(msg_dict)
            pubsub_utils.publish(msg=msg, topic_id=pubsub_utils.requestfulllabeling_topic())

    return 'OK', 200


@app.route('/label_one')
def label_one():
    """Pubsub push endpoint for messages from the Log Sink"""
    __check_pubsub_verification_token()

    envelope = flask.request.get_json()
    if not envelope:
        raise ValueError('Expect JSON')
    b64encoded_json: str = envelope['message']['data']
    data: typing.Dict = json.loads(base64.b64decode(b64encoded_json))
    __label_one_from_logline(data)
    return 'OK', 200


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
                    else:
                        logging.info('Cannot find %s to label', utils.shorten(str(data), 300))


@app.route('/do_label', methods=[ 'POST'])
def do_label():
    """ Receive a push message from PubSub, sent fromschedule() above,
     with instructions to label all objects of a given plugin and project_id.
    """
    try:
     __check_pubsub_verification_token()
    except ValueError as ve:
        return str(ve), 403

    envelope: typing.Dict = flask.request.get_json()
    if not envelope:
        raise ValueError('Expect JSON,  %s', envelope)
    data: typing.Dict = json.loads(base64.b64decode(envelope['message']['data']))

    plugin_name = data['plugin']
    cls = cls_by_name(PLUGINS_MODULE + '.' + plugin_name.lower() + '.' + plugin_name)
    project_id = data['project_id']
    logging.info("do_label() for %s in %s", cls.__name__, project_id)
    plugin = cls()
    plugin.do_label(project_id, **flask.request.args)
    return 'OK', 200


def __check_pubsub_verification_token():
    token = os.environ.get('PUBSUB_VERIFICATION_TOKEN', '')
    if not token:
        raise ValueError('Should define token in env %s',os.environ)
    if token != flask.request.args.get('token', ''):
        raise ValueError(f'Invalid PubSub token "{token}"')


if __name__ in ['__main__']:
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    port = os.environ.get('PORT', '8000')
    logging.info('Running __main__ for main.py, port %s', port)
    port = int(port)
    app.run(host="127.0.0.1", port=port, debug=True)
