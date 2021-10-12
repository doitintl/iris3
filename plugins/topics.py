import logging
import re
import typing

from google.cloud import pubsub_v1
from googleapiclient import errors

from plugin import Plugin
from util.utils import log_time, timing


class Topics(Plugin):
    __topic_client = pubsub_v1.PublisherClient()
    __topic_path_regex = re.compile(r"^projects/[^/]+/topics/[^/]+$")

    @classmethod
    def discovery_api(cls) -> typing.Tuple[str, str]:
        return "pubsub", "v1"

    def api_name(self):
        return "pubsub.googleapis.com"

    def method_names(self):
        # Actually longer name, but substring is allowed
        return ["Publisher.CreateTopic"]

    def label_all(self, project_id):
        with timing(f"label_all(Topic)  in {project_id}"):
            topics = self.__list_topics(project_id)
            for topics in topics:
                try:
                    self.label_resource(topics, project_id)
                except Exception as e:
                    logging.exception(e)

    def __get_topic(self, topic_path):

        assert self.__topic_path_regex.match(topic_path)
        try:
            result = (
                self._google_client.projects().topics().get(topic=topic_path).execute()
            )
            return result
        except errors.HttpError as e:
            logging.exception(e)
            return None

    def __list_topics(self, project_id):

        topics = []
        page_token = None
        while True:
            result = (
                self._google_client.projects()
                .topics()
                .list(
                    project=f"projects/{project_id}",
                    pageToken=page_token
                    # No filter param availble
                )
                .execute()
            )
            if "topics" in result:
                topics += result["topics"]
            if "nextPageToken" in result:
                page_token = result["nextPageToken"]
            else:
                break

        return topics

    @log_time
    def label_resource(self, gcp_object: typing.Dict, project_id):
        # This API does not accept label-fingerprint, so extracting just labels
        labels_outer = self._build_labels(gcp_object, project_id)
        if labels_outer is None:
            return
        labels = labels_outer["labels"]

        topic_name = self._gcp_name(gcp_object)
        topic_path = self.__topic_client.topic_path(project_id, topic_name)
        # We use the Google Cloud Library instead of the Google Client API used
        # elsewhere because the latter does not seem to support changing the label,
        # or at least I could not figure it out.
        topic_object_holding_update = pubsub_v1.types.Topic(
            name=topic_path, labels=labels
        )

        update_mask = {"paths": {"labels"}}

        with timing("update topic"):
            _ = self.__topic_client.update_topic(
                request={
                    "topic": topic_object_holding_update,
                    "update_mask": update_mask,
                }
            )

        logging.info(f"Topic updated: {topic_path}")

    def get_gcp_object(self, log_data):
        try:
            topic_path = log_data["protoPayload"]["request"]["name"]
            topic = self.__get_topic(topic_path)
            return topic
        except Exception as e:
            logging.exception(e)
            return None

    def _gcp_name(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        return self._name_after_slash(gcp_object)
