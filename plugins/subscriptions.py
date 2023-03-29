import logging
import re
import typing
from functools import lru_cache

from google.cloud import pubsub_v1
from google.pubsub_v1 import SubscriberClient
from googleapiclient import errors

from plugin import Plugin
from util.gcp_utils import (
    cloudclient_pb_obj_to_dict,
    cloudclient_pb_objects_to_list_of_dicts,
)
from util.utils import log_time
from util.utils import timing


class Subscriptions(Plugin):
    __sub_path_regex = re.compile(r"^projects/[^/]+/subscriptions/[^/]+$")

    @staticmethod
    @lru_cache(maxsize=1)
    def _cloudclient() -> SubscriberClient:
        return pubsub_v1.SubscriberClient()

    @staticmethod
    def _discovery_api() -> typing.Tuple[str, str]:
        """Not used"""
        return "pubsub", "v1"

    # @staticmethod
    # def api_name():
    #     return "pubsub.googleapis.com"

    @staticmethod
    def method_names():
        # Actually "google.pubsub.v1.Subscriber.CreateSubscription" but a
        # substring is allowed
        return ["Subscriber.CreateSubscription"]

    def label_all(self, project_id):
        with timing(f"label_all(Subscription)  in {project_id}"):
            subs = self.__list_subscriptions(project_id)
            for sub in subs:
                try:
                    self.label_resource(sub, project_id)
                except Exception as e:
                    logging.exception(e)
            if self.counter > 0:
                self.do_batch()

    def __get_subscription(self, subscription_path):
        assert self.__sub_path_regex.match(subscription_path)
        try:
            subsc = self._cloudclient().get_subscription(subscription=subscription_path)

            return cloudclient_pb_obj_to_dict(subsc)

        except errors.HttpError as e:
            logging.exception(e)
            return None

    def __list_subscriptions(self, project_id):
        project_path = f"projects/{project_id}"
        subscriptions = self._cloudclient().list_subscriptions(
            request={"project": project_path}
        )
        return cloudclient_pb_objects_to_list_of_dicts(
            subscriptions
        )  # TODO could make this lazy

    @log_time
    def label_resource(self, gcp_object: typing.Dict, project_id):
        labels_outer = self._build_labels(gcp_object, project_id)
        if labels_outer is None:
            return
        labels = labels_outer["labels"]

        subscription_name = self._gcp_name(gcp_object)
        topic = gcp_object["topic"].split("/")[-1]

        subscription_path = self._cloudclient().subscription_path(
            project_id, subscription_name
        )
        # Use the Google Cloud Library instead of the Google Client API used
        #   because the latter does not seem to support changing the label,
        subscription_object_holding_update = pubsub_v1.types.Subscription(
            name=subscription_path, topic=topic, labels=labels
        )

        update_mask = {"paths": {"labels"}}

        with self._cloudclient():
            with timing("update subscription"):
                _ = self._cloudclient().update_subscription(
                    request={
                        "subscription": subscription_object_holding_update,
                        "update_mask": update_mask,
                    }
                )

        logging.info(f"Subscription updated: {subscription_path}")

    def get_gcp_object(self, log_data):
        try:
            subscription_path = log_data["protoPayload"]["request"]["name"]
            subscription = self.__get_subscription(subscription_path)
            return subscription
        except Exception as e:
            logging.exception(e)
            return None

    def _gcp_name(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        return self._name_after_slash(gcp_object)
