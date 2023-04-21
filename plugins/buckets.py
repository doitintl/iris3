import logging
from functools import lru_cache

from plugin import Plugin
from util import gcp_utils
from util.gcp_utils import add_loaded_lib
from util.utils import log_time, timing, dict_to_camelcase


class Buckets(Plugin):
    @staticmethod
    def _discovery_api():
        return "storage", "v1"

    @staticmethod
    def method_names():
        return ["storage.buckets.create"]

    @classmethod
    @lru_cache(maxsize=500)  # cached per project
    def _cloudclient(cls, project_id=None):
        assert project_id, "'None' is only for the signature"
        logging.info("_cloudclient for %s", cls.__name__)
        # Local import to avoid burdening AppEngine memory.
        # Loading all Cloud Client libraries would be 100MB  means that
        # the default AppEngine Instance crashes on out-of-memory even before actually serving a request.
        from google.cloud import storage

        add_loaded_lib("storage")
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
        except KeyError:
            logging.exception("")
            return None

    def _get_resource(self, bucket_name, project_id):
        try:
            bucket_response = self._cloudclient(project_id).get_bucket(
                bucket_or_name=bucket_name
            )
            ret = self.__response_obj_to_dict(bucket_response)
            return ret

        except Exception:
            logging.exception("")
            return None

    def get_gcp_object(self, log_data):
        buck_name = log_data["resource"]["labels"]["bucket_name"]
        project_id = log_data["resource"]["labels"]["project_id"]

        bucket = self._get_resource(buck_name, project_id)
        try:
            return bucket
        except Exception:
            logging.exception("")
            return None

    @staticmethod
    def __response_obj_to_dict(bucket_response):
        d1 = bucket_response._properties  # Is this meeded:| bucket_response.__dict__
        d2 = {k: v for k, v in d1.items() if not k.startswith("_")}
        d3 = dict_to_camelcase(d2)
        return d3

    def _list_all(self, project_id):
        buckets = self._cloudclient(project_id).list_buckets()
        return (
            self.__response_obj_to_dict(bucket_response) for bucket_response in buckets
        )

    def label_all(self, project_id):
        with timing(f"label_all(Bucket) in {project_id}"):
            for o in self._list_all(project_id):
                try:
                    self.label_resource(o, project_id)
                except Exception:
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
        except Exception:
            logging.exception("")
