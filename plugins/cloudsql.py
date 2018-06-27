import logging

from google.auth import app_engine
from googleapiclient import discovery, errors

from pluginbase import Plugin
from utils import gcp

SCOPES = ['https://www.googleapis.com/auth/sqlservice.admin']

CREDENTIALS = app_engine.Credentials(scopes=SCOPES)


class CloudSql(Plugin):

    def register_signals(self):
        self.sqladmin = discovery.build(
            'sqladmin', 'v1beta4', credentials=CREDENTIALS)
        logging.debug("Cloud SQL class created and registering signals")


    def do_tag(self, project_id):
        page_token = None
        more_results = True
        while more_results:
            response = self.sqladmin.instances().list(
                project=project_id, pageToken=page_token).execute()
            if 'items' not in response:
                return
            for database_instance in response['items']:
                database_instance_body = {
                    "settings": {
                        "userLabels": {
                            gcp.get_name_tag():
                                database_instance['name'].replace(".",
                                                                  "_").lower(),
                            gcp.get_zone_tag(): database_instance[
                                "gceZones"].lower(),
                            gcp.get_region_tag(): gcp.region_from_zone(
                                database_instance["gceZones"]).lower(),
                        }
                    }
                }
                try:
                    self.sqladmin.instances().patch(
                        project=project_id,
                        instance=database_instance['name'],
                        body=database_instance_body).execute()
                except errors.HttpError as e:
                    logging.error(e)
            if 'nextPageToken' in response:
                page_token = response['nextPageToken']
            else:
                more_results = False
