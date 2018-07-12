import logging

from google.auth import app_engine
from googleapiclient import discovery, errors

from pluginbase import Plugin
from utils import utils

SCOPES = ['https://www.googleapis.com/auth/devstorage.full_control']

CREDENTIALS = app_engine.Credentials(scopes=SCOPES)


class Gcs(Plugin):
    def __init__(self):
        Plugin.__init__(self)
        self.storage = discovery.build(
            'storage', 'v1', credentials=CREDENTIALS)
        self.batch = self.storage.new_batch_http_request(
            callback=self.batch_callback)


    def register_signals(self):

        logging.debug("Storage class created and registering signals")


    def _get_name(self, gcp_object):
        try:
            name = gcp_object['name']
            name = name.replace(".", "_").lower()[:62]
        except KeyError as e:
            logging.error(e)
            return None
        return name


    def _get_location(self, gcp_object):
        try:
            location = gcp_object['location']
            location = location.replace(".", "_").lower()
        except KeyError as e:
            logging.error(e)
            return None
        return location


    def api_name(self):
        return "storage-component.googleapis.com"


    def methodsNames(self):
        return ["storage.buckets.create"]


    def get_bucket(self, bucket_name):
        try:
            result = self.storage.buckets().get(
                bucket=bucket_name).execute()
        except errors.HttpError as e:
            logging.error(e)
            return None
        return result


    def get_gcp_object(self, data):
        try:
            bucket = self.get_bucket(
                data['resource']['labels']['bucket_name'])
            return bucket
        except Exception as e:
            logging.error(e)
            return None


    def do_tag(self, project_id):

        page_token = None
        more_results = True
        while more_results:
            try:
                response = self.storage.buckets().list(
                    project=project_id, pageToken=page_token).execute()
            except errors.HttpError as e:
                logging.error(e)
                return
            if 'items' in response:
                for bucket in response['items']:
                    self.tag_one(bucket, project_id)
            if 'nextPageToken' in response:
                page_token = response['nextPageToken']
            else:
                more_results = False
        if self.counter > 0:
            self.do_batch()


    def tag_one(self, gcp_object, project_id):
        labels = dict()
        labels['labels'] = self.gen_labels(gcp_object)
        try:
            self.batch.add(self.storage.buckets().patch(
                bucket=gcp_object['name'], body=labels),
                request_id=utils.get_uuid())
            self.counter = self.counter + 1
            if self.counter == 1000:
                self.do_batch()
        except Exception as e:
            logging.error(e)
        return 'ok', 200
