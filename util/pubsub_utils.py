import logging

from google.api_core.exceptions import AlreadyExists
from google.cloud import pubsub_v1

from util import conf_utils
from util import gcp_utils

__publisher = pubsub_v1.PublisherClient()


def create_subscriptions(callback_endpoint_path, topic):
    subscriber = pubsub_v1.SubscriberClient()
    with subscriber:
        endpoint = gcp_utils.gae_url(callback_endpoint_path)
        topic_path = __publisher.topic_path(gcp_utils.project_id(), topic)
        subscription_path = subscriber.subscription_path(gcp_utils.project_id(), callback_endpoint_path)

        push_config = pubsub_v1.types.PushConfig(push_endpoint=endpoint)
        try:
            _subscription = subscriber.create_subscription(
                request={'name': subscription_path,
                         'topic': topic_path, 'push_config': push_config, })
            logging.info(
                'Created subscription endpoint %s on topic %s in project %s ',
                callback_endpoint_path, topic, gcp_utils.project_id())
        except AlreadyExists:
            logging.info('Subscription %s already exists', callback_endpoint_path)


def logs_topic() -> str:
    return f'{conf_utils.iris_prefix()}_logs_topic'


def scheduled_labeling_topic() -> str:
    return f'{conf_utils.iris_prefix()}_scheduled_labeling_topic'


def publish(project_id: str, msg: str, topic_id: str):
    topic_path = __publisher.topic_path(project_id, topic_id)

    def callback_func(f):
        try:
            logging.info(f.result())
        except Exception as e:
            logging.exception(e)

    future = __publisher.publish(topic_path, msg.encode("utf-8"))
    future.add_done_callback(callback_func)

    print(f"Published message to {topic_path}.")
