import logging

from googleapiclient import discovery, errors

from pluginbase import Plugin
from util import gcp_utils

google_client = discovery.build('storage', 'v1')


class Gcs(Plugin):
    # TODO: Test label_one with sample log json; test in cloud
    def __init__(self):
        super().__init__()

        self.batch = google_client.new_batch_http_request(
            callback=self.batch_callback)

    def _get_name(self, gcp_object):
        """Method dynamically called in _gen_labels, so don't change name"""
        try:
            name = gcp_object['name']
            name = name.replace(".", "_").lower()[:62]
            return name
        except KeyError as e:
            logging.error(e)
            return None

    def _get_location(self, gcp_object):
        """Method dynamically called in _gen_labels, so don't change name"""
        try:
            location = gcp_object['location']
            location = location.replace(".", "_").lower()
            return location
        except KeyError as e:
            logging.error(e)
            return None

    def api_name(self):
        return "storage-component.googleapis.com"

    def method_names(self):
        return ["storage.buckets.create"]

    def __get_bucket(self, bucket_name):
        try:
            result = google_client.buckets().get(
                bucket=bucket_name).execute()
            return result
        except errors.HttpError as e:
            logging.exception(e)
            return None

    def get_gcp_object(self, data):
        try:
            bucket = self.__get_bucket(
                data['resource']['labels']['bucket_name'])
            return bucket
        except Exception as e:
            logging.error(e)
            return None

    def do_label(self, project_id):

        page_token = None
        more_results = True
        while more_results:
            try:
                response = google_client.buckets().list(
                    project=project_id, pageToken=page_token).execute()
            except errors.HttpError as e:
                logging.error(e)
                return
            if 'items' in response:
                for bucket in response['items']:
                    self.label_one(bucket, project_id)
            if 'nextPageToken' in response:
                page_token = response['nextPageToken']
            else:
                more_results = False
        if self.counter > 0:
            self.do_batch()

    def label_one(self, gcp_object, project_id):
        labels = {'labels': self._gen_labels(gcp_object)}
        try:
            self.batch.add(google_client.buckets().patch(
                bucket=gcp_object['name'], body=labels),
                request_id=gcp_utils.generate_uuid())
            self.counter += 1
            if self.counter == 1000:
                self.do_batch()
        except Exception as e:
            logging.error(e)
        return 'OK', 200
