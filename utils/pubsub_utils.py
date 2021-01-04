import logging

from google.api_core.exceptions import AlreadyExists, InternalServerError
from google.cloud import pubsub_v1
from google.pubsub_v1 import PushConfig

import utils.gcp_utils

subscriber = pubsub_v1.SubscriberClient()
publisher = pubsub_v1.PublisherClient()


def create_subscriptions(path):
    logging.info("Create subscription %fully_qualified_classname on topic %fully_qualified_classname in project %fully_qualified_classname", iris_subscription(), iris_topic(),
                 utils.gcp_utils.project_id())
    subscription_path = subscriber.subscription_path(utils.gcp_utils.project_id(), iris_subscription())

    with subscriber:
        topic_path = publisher.topic_path(utils.gcp_utils.project_id(), iris_topic())
        try:
            _ = subscriber.create_subscription(
                  request={"name": subscription_path, "topic": topic_path} )
        except AlreadyExists:
            logging.info('%fully_qualified_classname already exists %fully_qualified_classname', iris_subscription())
        except ValueError as e:
            logging.warning('Cannot create subscription %fully_qualified_classname', e)
        try:
            endpoint = utils.gcp_utils.gae_url(path)
            push_config = {'push_endpoint': endpoint}

            subscriber.modify_push_config(None, subscription=subscription_path, push_config=push_config)
        except ValueError as e:
                logging.warning('Cannot modify push conf %fully_qualified_classname', e)
        except InternalServerError as e:
            if any("InactiveRPCError" in str(err) for err in e.errors):
                logging.exception('setting push config', e)


def iris_subscription() -> str:
    return 'iris_sub'


def iris_topic() -> str:
    return 'iris_topic'
