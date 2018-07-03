import logging

from google.auth import app_engine
from googleapiclient import discovery, errors

from pluginbase import Plugin
from utils import gcp

SCOPES = ['https://www.googleapis.com/auth/devstorage.full_control']

CREDENTIALS = app_engine.Credentials(scopes=SCOPES)


class Gcs(Plugin):

    def register_signals(self):
        self.storage = discovery.build(
            'storage', 'v1', credentials=CREDENTIALS)
        logging.debug("Storage class created and registering signals")


    def api_name(self):
        return "storage-component.googleapis.com"

    def do_tag(self, project_id):
        page_token = None
        more_results = True
        while more_results:
            response = self.storage.buckets().list(
                project=project_id, pageToken=page_token).execute()
            if 'items' in response:
                for bucket in response['items']:
                    gcs_body = {
                        "labels": {
                            gcp.get_name_tag(): bucket['name'].replace(".",
                                                                       "_").lower(),
                            gcp.get_loc_tag(): bucket['location'].lower(),
                        }
                    }
                    try:
                        self.storage.buckets().patch(
                            bucket=bucket['name'], body=gcs_body).execute()
                    except errors.HttpError as e:
                        logging.error(e)

            if 'nextPageToken' in response:
                page_token = response['nextPageToken']
            else:
                more_results = False
