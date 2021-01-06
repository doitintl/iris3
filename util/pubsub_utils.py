import logging
import textwrap

from google.api_core.exceptions import AlreadyExists, NotFound
from google.cloud import pubsub_v1

from util import config_utils
from util import gcp_utils

__publisher = pubsub_v1.PublisherClient()


def create_subscription(subsc, topic):
    subscriber = pubsub_v1.SubscriberClient()
    with subscriber:
        path = subsc + gcp_utils.environment_suffix()
        subscription_path = subscriber.subscription_path(gcp_utils.project_id(), path)
        try:
            subscriber.delete_subscription(request={"subscription": subscription_path})
            logging.info(f'Subscription deleted: {subscription_path}')
        except NotFound as e:
            logging.debug(e)  # OK, nothing to delete

        endpoint = gcp_utils.gae_url(subsc)
        topic_path = __publisher.topic_path(gcp_utils.project_id(), topic)

        push_config = pubsub_v1.types.PushConfig(push_endpoint=endpoint)
        try:
            _subscription = subscriber.create_subscription(
                request={'name': subscription_path,
                         'topic': topic_path,
                         'push_config': push_config, })
            logging.info(
                'Created subscription %s  %s (%s) in %s ',
                endpoint, subscription_path, topic, gcp_utils.project_id())
        except AlreadyExists:
            logging.info('Subscription %s (%s) already exists', subscription_path, endpoint)


def logs_topic() -> str:
    return f'{config_utils.iris_prefix()}_logs_topic'


def request_full_labeling_topic() -> str:
    return f'{config_utils.iris_prefix()}_request_full_labeling_topic'


def publish(msg: str, topic_id: str):
    topic_path = __publisher.topic_path(gcp_utils.project_id(), topic_id)

    def on_publish(f):
        try:
            result = f.result()
            try:
                int(result)  # Int results indicate success, no need to log
            except ValueError as e:  # not an int, failed
                logging.info('PubSub publishing result %s', result)
        except Exception as e:
            logging.exception(e)

    future = __publisher.publish(topic_path, msg.encode('utf-8'))
    future.add_done_callback(on_publish)

    logging.info('Published message to %s: %s', topic_path, textwrap.shorten(msg, 200))
