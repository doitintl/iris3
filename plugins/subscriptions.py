import logging
import re
import typing

from google.cloud import pubsub_v1
from googleapiclient import errors

from plugin import Plugin


class Subscriptions(Plugin):
    __sub_path_regex = re.compile(r"^projects/[^/]+/subscriptions/[^/]+$")

    @classmethod
    def discovery_api(cls) -> typing.Tuple[str, str]:
        return "pubsub", "v1"

    def api_name(self):
        return "pubsub.googleapis.com"

    def method_names(self):
        # Actually "google.pubsub.v1.Subscriber.CreateSubscription" but a
        # substring is allowed
        return ["Subscriber.CreateSubscription"]

    def do_label(self, project_id):
        subs = self.__list_subscriptions(project_id)
        for sub in subs:

            self.label_one(sub, project_id)
        return "OK", 200

    def __get_subscription(self, subscription_path):

        assert self.__sub_path_regex.match(subscription_path)
        try:
            result = (
                self._google_client.projects()
                .subscriptions()
                .get(
                    subscription=subscription_path,
                )
                .execute()
            )
            return result
        except errors.HttpError as e:
            logging.exception(e)
            return None

    def __list_subscriptions(self, project_id):

        subscriptions = []
        page_token = None
        while True:
            try:
                result = (
                    self._google_client.projects()
                    .subscriptions()
                    .list(
                        project=f"projects/{project_id}",
                        pageToken=page_token,
                        # No filter param
                    )
                    .execute()
                )
                if "subscriptions" in result:
                    subscriptions += result["subscriptions"]
                if "nextPageToken" in result:
                    page_token = result["nextPageToken"]
                else:
                    break
            except errors.HttpError as e:
                logging.exception(e)

        return subscriptions

    def label_one(self, gcp_object: typing.Dict, project_id):
        assert isinstance(gcp_object, dict), type(gcp_object)
        labels_outer = self._build_labels(gcp_object, project_id)
        labels = labels_outer["labels"]
        try:
            subscription_name = self._get_name(gcp_object)
            topic = gcp_object["topic"].split("/")[-1]
            subscriber_client = pubsub_v1.SubscriberClient()
            subscription_path = subscriber_client.subscription_path(
                project_id, subscription_name
            )
            # Use the Google Cloud Library instead of the Google Client API used
            # elsewhere because the latter does not seem to support changing the label,
            # or at least I could not figure it out.
            subscription_object_holding_update = pubsub_v1.types.Subscription(
                name=subscription_path, topic=topic, labels=labels
            )

            update_mask = {"paths": {"labels"}}

            with subscriber_client:
                _ = subscriber_client.update_subscription(
                    request={
                        "subscription": subscription_object_holding_update,
                        "update_mask": update_mask,
                    }
                )

            logging.info(f"Subscription updated: {subscription_path}")

        except errors.HttpError as e:
            logging.exception(e)
            return "Error", 500
        return "OK", 200

    def get_gcp_object(self, data):
        try:
            subscription_path = data["protoPayload"]["request"]["name"]
            subscription = self.__get_subscription(subscription_path)
            return subscription
        except Exception as e:
            logging.exception(e)
            return None

    def _get_name(self, gcp_object):
        """Method dynamically called in __generate_labels, so don't change name"""
        return self._name_after_slash(gcp_object)
