"""Interact with pub/sub."""
import logging

import backoff
from google.auth import app_engine
from googleapiclient import discovery
from googleapiclient.errors import HttpError

import utils

PUBSUB_SCOPES = [
    'https://www.googleapis.com/auth/pubsub',
    'https://www.googleapis.com/auth/cloud-platform'
]
CREDENTIALS = app_engine.Credentials(scopes=PUBSUB_SCOPES)


class PubSubException(Exception):
    """Exception class for Pub/Sub functions."""

    def __init__(self, value):
        self.parameter = value

    def __str__(self):
        return repr(self.parameter)


def get_pubsub_client():
    """Get a pubsub client from the API."""
    return discovery.build('pubsub', 'v1', credentials=CREDENTIALS)


def publish(client, body, topic):
    """Publish a message to a Pub/Sub topic."""
    project = 'projects/{}'.format(utils.get_project_id())
    dest_topic = project + '/topics/' + topic

    @backoff.on_exception(
        backoff.expo, HttpError, max_tries=3, giveup=utils.fatal_code)
    def _do_request():
        client.projects().topics().publish(
            topic=dest_topic, body=body).execute()

    try:
        _do_request()
    except HttpError as e:
        logging.error(e)
        raise PubSubException(e)


def create_subscriptions(client, sub, topic):
    """
    Create a subscription in pub/sub.

    :param client:
    :param sub:
    :param topic:
    :return:
    """
    project = 'projects/{}'.format(utils.get_project_id())
    dest_sub = project + '/subscriptions/' + sub
    dest_topic = project + '/topics/' + topic
    body = {'topic': dest_topic}
    logging.info("Create topic %sub on topic %s in project %s",sub, topic, project)
    def _do_get_request():
        return client.projects().subscriptions().get(
            subscription=dest_sub).execute()

    @backoff.on_exception(
        backoff.expo, HttpError, max_tries=3, giveup=utils.fatal_code)
    def _do_create_request():
        res = client.projects().subscriptions().create(
            name=dest_sub, body=body).execute()
        logging.debug(res)

    try:
        _do_get_request()
    except Exception as e:
        if e.resp.status == 404:
            logging.error(e)
            _do_create_request()
        else:
            logging.error(e)
            raise PubSubException(e)


def create_topic(client, topic):
    """
    Check if topix exists if not create it.

    :param client:
    :param topic:
    :return:
    """
    project = 'projects/{}'.format(utils.get_project_id())
    dest_topic = project + '/topics/' + topic

    @backoff.on_exception(
        backoff.expo, HttpError, max_tries=3, giveup=utils.fatal_code)
    def _do_get_request():
        return client.projects().topics().get(topic=dest_topic).execute()

    @backoff.on_exception(
        backoff.expo, HttpError, max_tries=3, giveup=utils.fatal_code)
    def _do_create_request():
        client.projects().topics().create(name=dest_topic, body={}).execute()

    try:
        _do_get_request()
    except HttpError as e:
        if e.resp.status == 404:
            _do_create_request()
        else:
            logging.error(e)
            raise PubSubException(e)


def fqrn(resource_type, project, resource):
    """Return a fully qualified resource name for Cloud Pub/Sub."""
    return 'projects/{}/{}/{}'.format(project, resource_type, resource)


def get_full_subscription_name(project, subscription):
    """Return a fully qualified subscription name."""
    return fqrn('subscriptions', project, subscription)


def pull(client, sub, endpoint):
    """Register a listener endpoint."""
    subscription = get_full_subscription_name(utils.get_project_id(), sub)
    body = {'pushConfig': {'pushEndpoint': endpoint}}

    @backoff.on_exception(
        backoff.expo, HttpError, max_tries=3, giveup=utils.fatal_code)
    def _do_request():
        client.projects().subscriptions().modifyPushConfig(
            subscription=subscription, body=body).execute()

    try:
        _do_request()
    except HttpError as e:

        logging.error(e)
        return 'Error', 500
    return 'ok, 204'
