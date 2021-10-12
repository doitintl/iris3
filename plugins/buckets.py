import logging
import typing

from plugin import Plugin
from util import gcp_utils
from util.utils import log_time, timing


class Buckets(Plugin):
    @classmethod
    def discovery_api(cls) -> typing.Tuple[str, str]:
        return "storage", "v1"

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
            logging.exception(e)
            return None

    def api_name(self):
        return "storage-component.googleapis.com"

    def method_names(self):
        return ["storage.buckets.create"]

    def __get_bucket(self, bucket_name):
        try:
            result = self._google_client.buckets().get(bucket=bucket_name).execute()

            return result
        except Exception as e:
            logging.exception(e)
            return None

    def get_gcp_object(self, log_data):
        try:
            bucket = self.__get_bucket(log_data["resource"]["labels"]["bucket_name"])
            return bucket
        except Exception as e:
            logging.exception(e)
            return None

    def label_all(self, project_id):
        with timing(f"label_all(Bucket) in {project_id}"):
            page_token = None
            more_results = True
            while more_results:
                response = (
                    self._google_client.buckets()
                    .list(
                        project=project_id,
                        pageToken=page_token,
                        # filter not supported
                    )
                    .execute()
                )
                if "items" in response:
                    for bucket in response["items"]:
                        try:
                            self.label_resource(bucket, project_id)
                        except Exception as e:
                            logging.exception(e)
                if "nextPageToken" in response:
                    page_token = response["nextPageToken"]
                else:
                    more_results = False
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
                self._google_client.buckets().patch(bucket=bucket_name, body=labels),
                request_id=gcp_utils.generate_uuid(),
            )
            self.counter += 1
            if self.counter >= self._BATCH_SIZE:
                self.do_batch()
        except Exception as e:
            logging.exception(e)
