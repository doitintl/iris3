import logging
import typing
from functools import lru_cache

from google.cloud import storage

from plugin import Plugin
from util import gcp_utils
from util.gcp_utils import cloudclient_pb_objects_to_list_of_dicts
from util.utils import log_time, timing, dict_to_camelcase


class Buckets(Plugin):
    @staticmethod
    def _discovery_api() -> typing.Tuple[str, str]:
        return "storage", "v1"

    # @staticmethod
    # def api_name():
    #     return "storage-component.googleapis.com"

    @staticmethod
    def method_names():
        return ["storage.buckets.create"]

    @staticmethod
    @lru_cache(maxsize=500)  # cached per project
    def _cloudclient(project_id):
        return storage.Client(project=project_id)

    def _gcp_name(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        return self._name_no_separator(gcp_object)

    def _gcp_location(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            location = gcp_object["location"]
            location = location.replace(".", "_").lower()
            return location
        except KeyError as e:
            logging.exception("")
            return None

    def __get_bucket(self, bucket_name, project_id):
        try:
            bucket = self._cloudclient(project_id).get_bucket(
                bucket_or_name=bucket_name
            )
            d1 = bucket._properties | bucket.__dict__
            d2 = {k: v for k, v in d1.items() if not k.startswith("_")}
            d3 = dict_to_camelcase(d2)
            return d3

        except Exception as e:
            logging.exception("")
            return None

    def get_gcp_object(self, log_data):
        buck_name = log_data["resource"]["labels"]["bucket_name"]
        project_id = log_data["resource"]["labels"]["project_id"]

        bucket = self.__get_bucket(buck_name, project_id)
        try:
            return bucket
        except Exception as e:
            logging.exception("")
            return None

    def __list_buckets(self, project_id):
        buckets = self._cloudclient(project_id).list_buckets()
        return cloudclient_pb_objects_to_list_of_dicts(buckets)

    def label_all(self, project_id):  # TODO extract this code for general use
        with timing(f"label_all(Bucket) in {project_id}"):
            buckets = self.__list_buckets(project_id)
            for bucket in buckets:
                try:
                    self.label_resource(bucket, project_id)
                except Exception as e:
                    logging.exception("")
            if self.counter > 0:
                self.do_batch()

    @log_time
    def label_resource(self, gcp_object, project_id):

        labels = self._build_labels(gcp_object, project_id)
        if labels is None:
            return

        try:
            bucket_name = gcp_object["name"]

            self._batch.add(
                self._google_api_client()
                .buckets()
                .patch(bucket=bucket_name, body=labels),
                request_id=gcp_utils.generate_uuid(),
            )
            self.counter += 1
            if self.counter >= self._BATCH_SIZE:
                self.do_batch()
        except Exception as e:
            logging.exception("")
