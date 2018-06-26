import logging

from google.auth import app_engine
from googleapiclient import discovery

from utils import gcp
from pluginbase import Plugin

SCOPES = ['https://www.googleapis.com/auth/devstorage.full_control']

CREDENTIALS = app_engine.Credentials(scopes=SCOPES)


class Gcs(Plugin):

    def register_signals(self):
        self.storage = discovery.build(
            'storage', 'v1', credentials=CREDENTIALS)
        logging.debug("Storage class created and registering signals")

    def do_tag(self, project_id):
        page_token = None
        more_results = True
        while more_results:
            response = self.storage.buckets().list(
                project=project_id, pageToken=page_token).execute()
            for bucket in response['items']:
                gcs_body = {
                    "labels": {
                        gcp.get_name_tag(): bucket['name'].replace(".", "_"),
                        gcp.get_loc_tag(): bucket['location'].lower(),
                    }
                }
                self.storage.buckets().patch(
                    bucket=bucket['name'], body=gcs_body).execute()

            if 'nextPageToken' in response:
                page_token = response['nextPageToken']
            else:
                more_results = False
