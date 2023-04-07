import logging
import re
from functools import lru_cache
from typing import Tuple, List, Dict

from google.cloud import pubsub_v1
from google.pubsub_v1 import Topic
from googleapiclient import errors

from plugin import Plugin
from util.gcp_utils import (
    cloudclient_pb_obj_to_dict,
    cloudclient_pb_objects_to_list_of_dicts,
)
from util.utils import log_time, timing


class Topics(Plugin):
    __topic_path_regex = re.compile(r"^projects/[^/]+/topics/[^/]+$")

    @staticmethod
    @lru_cache(maxsize=1)
    def _cloudclient():
        return pubsub_v1.PublisherClient()

    @staticmethod
    def _discovery_api() -> Tuple[str, str]:
        return "pubsub", "v1"

    def method_names(self):
        # Actually the name is longer  , but substring is allowed
        return ["Publisher.CreateTopic"]

    def label_all(self, project_id):
        with timing(f"label_all(Topic  in {project_id}"):
            topics = self.__list_topics(project_id)
            for topics in topics:
                try:
                    self.label_resource(topics, project_id)
                except Exception as e:
                    logging.exception("")

    def __get_topic(self, topic_path):
        try:
            assert self.__topic_path_regex.match(topic_path)
            topic: Topic = self._cloudclient().get_topic(topic=topic_path)
            return cloudclient_pb_obj_to_dict(topic)
        except errors.HttpError as e:
            logging.exception("")
            return None

    def __list_topics(self, project_id) -> List[Dict]:
        project_path = f"projects/{project_id}"
        topics = self._cloudclient().list_topics(request={"project": project_path})
        return cloudclient_pb_objects_to_list_of_dicts(topics)

    @log_time
    def label_resource(self, gcp_object: Dict, project_id):
        # This API does not accept label-fingerprint, so extracting just labels
        labels_outer = self._build_labels(gcp_object, project_id)
        if labels_outer is None:
            return
        labels = labels_outer["labels"]

        topic_name = self._gcp_name(gcp_object)
        topic_path = self._cloudclient().topic_path(project_id, topic_name)

        topic_object_holding_update = pubsub_v1.types.Topic(
            name=topic_path, labels=labels
        )

        update_mask = {"paths": {"labels"}}

        with timing("update topic"):
            _ = self._cloudclient().update_topic(
                request={
                    "topic": topic_object_holding_update,
                    "update_mask": update_mask,
                }
            )

        logging.info(f"Topic updated: {topic_path}")

    def get_gcp_object(self, log_data: Dict) -> Dict:
        try:
            topic_path = log_data["protoPayload"]["request"]["name"]
            # path can be constructed with self._cloudclient().topic_path(project_id, topic_id)
            topic = self.__get_topic(topic_path)

            return topic
        except Exception as e:
            logging.exception("")
            return None

    def _gcp_name(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        return self._name_after_slash(gcp_object)
