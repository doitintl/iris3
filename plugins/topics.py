import logging
from functools import lru_cache
from typing import List, Dict, Optional

from googleapiclient import errors

from plugin import Plugin
from util.gcp_utils import (
    cloudclient_pb_obj_to_dict,
    cloudclient_pb_objects_to_list_of_dicts,
    add_loaded_lib,
)
from util.utils import log_time, timing


class Topics(Plugin):
    @classmethod
    @lru_cache(maxsize=1)
    def _cloudclient(cls, _=None):
        logging.info("_cloudclient for %s", cls.__name__)
        # Local import to avoid burdening AppEngine memory.
        # Loading all Cloud Client libraries would be 100MB  means that
        # the default AppEngine Instance crashes on out-of-memory even before actually serving a request.
        from google.cloud import pubsub_v1

        add_loaded_lib("pubsub_v1")

        return pubsub_v1.PublisherClient()

    @staticmethod
    def _discovery_api():
        """Discovery API not actually used with Topics. Would be "pubsub", "v1"""
        return None

    @staticmethod
    def method_names():
        # Actually"google.pubsub.v1.Subscriber.CreateTopic", but substring is allowed
        return ["Publisher.CreateTopic"]

    def label_all(self, project_id):
        with timing(f"label_all({type(self).__name__})  in {project_id}"):
            for o in self._list_all(project_id):
                try:
                    self.label_resource(o, project_id)
                except Exception:
                    logging.exception("")

    def __get_resource(self, path):
        try:
            o = self._cloudclient().get_topic(topic=path)
            return cloudclient_pb_obj_to_dict(o)
        except errors.HttpError:
            logging.exception("")
            return None

    def _list_all(self, project_id) -> List[Dict]:
        all_resources = self._cloudclient().list_topics(
            request={"project": f"projects/{project_id}"}
        )
        return cloudclient_pb_objects_to_list_of_dicts(all_resources)

    @log_time
    def label_resource(self, gcp_object: Dict, project_id):
        # This API does not accept label-fingerprint, so extracting just labels
        labels_outer = self._build_labels(gcp_object, project_id)
        if labels_outer is None:
            return
        labels = labels_outer["labels"]

        name = self._gcp_name(gcp_object)
        path = self._cloudclient().topic_path(project_id, name)
        # Local import to avoid burdening AppEngine memory.
        # Loading all Cloud Client libraries would be 100MB  means that
        # the default AppEngine Instance crashes on out-of-memory even before actually serving a request.
        from google.cloud import pubsub_v1

        add_loaded_lib("pubsub_v1")
        update_obj = pubsub_v1.types.Topic(name=path, labels=labels)

        update_mask = {"paths": {"labels"}}

        with timing("update " + type(self).__name__):
            _ = self._cloudclient().update_topic(
                request={
                    "topic": update_obj,
                    "update_mask": update_mask,
                }
            )

        logging.info(f"Updated: {path}")

    def get_gcp_object(self, log_data: Dict) -> Optional[Dict]:
        try:
            path = log_data["protoPayload"]["request"]["name"]
            return self.__get_resource(path)
        except Exception:
            logging.exception("")
            return None

    def _gcp_name(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        return self._name_after_slash(gcp_object)
