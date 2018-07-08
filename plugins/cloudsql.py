import logging

from google.auth import app_engine
from googleapiclient import discovery, errors

from pluginbase import Plugin
from utils import gcp, utils

SCOPES = ['https://www.googleapis.com/auth/sqlservice.admin']

CREDENTIALS = app_engine.Credentials(scopes=SCOPES)


class CloudSql(Plugin):

    def register_signals(self):
        self.sqladmin = discovery.build(
            'sqladmin', 'v1beta4', credentials=CREDENTIALS)
        logging.debug("Cloud SQL class created and registering signals")


    def api_name(self):
        return "sqladmin.googleapis.com"


    def do_tag(self, project_id):
        page_token = None
        more_results = True
        def batch_callback(request_id, response, exception):
            if exception is not None:
                logging.error(
                    'Error patching instance {0}: {1}'.format(request_id,
                                                           exception))
        counter = 0
        batch = self.sqladmin.new_batch_http_request(callback=batch_callback)
        while more_results:
            try:
                response = self.sqladmin.instances().list(
                    project=project_id, pageToken=page_token).execute()
            except errors.HttpError as e:
                logging.error(e)
                return
            if 'items' not in response:
                return
            for database_instance in response['items']:
                try:
                    database_instance_body = {
                        "settings": {
                            "userLabels": {
                                gcp.get_name_tag():
                                    database_instance['name'].replace(".",
                                                                      "_").lower()[:62],
                                gcp.get_zone_tag(): database_instance[
                                    "gceZones"].lower(),
                                gcp.get_region_tag(): gcp.region_from_zone(
                                    database_instance["gceZones"]).lower(),
                            }
                        }
                    }
                except Exception as e:
                    logging.error(e)
                    continue
                try:
                    batch.add(self.sqladmin.instances().patch(
                        project=project_id,
                        instance=database_instance['name'],
                        body=database_instance_body),request_id=utils.get_uuid())
                    counter = counter + 1
                    if counter == 1000:
                        batch.execute()
                        counter = 0
                except errors.HttpError as e:
                    logging.error(e)
            if 'nextPageToken' in response:
                page_token = response['nextPageToken']
            else:
                more_results = False
            if counter > 0:
                batch.execute()
