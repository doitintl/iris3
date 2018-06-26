""" Taging BQ tabels and datasets."""
import logging

from google.auth import app_engine
from googleapiclient import discovery

from pluginbase import Plugin
from utils import gcp

SCOPES = ['https://www.googleapis.com/auth/bigquery']

CREDENTIALS = app_engine.Credentials(scopes=SCOPES)


class BigQuery(Plugin):

    def register_signals(self):
        """
           Register with the plugin manager.
        """
        self.bigquery = discovery.build(
            'bigquery', 'v2', credentials=CREDENTIALS)
        logging.debug("BigQuery class created and registering signals")

    def do_tag(self, project_id):
        """
        tag tables and data sets
        :param project_id: project id
        """
        page_token = None
        more_results = True
        while more_results:
            response = self.bigquery.datasets().list(
                projectId=project_id, pageToken=page_token).execute()
            for dataset in response['datasets']:
                location = dataset['location']
                ds_body = {
                    "labels": {
                        gcp.get_loc_tag(): location,
                        gcp.get_name_tag(): dataset['datasetReference']['datasetId'].replace(".",
                                                                         "_"),
                    }
                }
                self.bigquery.datasets().patch(
                    projectId=project_id,
                    body=ds_body,
                    datasetId=dataset['datasetReference'][
                        'datasetId']).execute()
                if 'nextPageToken' in response:
                    page_token = response['nextPageToken']
                else:
                    more_results = False
                table_page_token = None
                table_more_results = True
                while table_more_results:
                    tresponse = self.bigquery.tables().list(
                        projectId=project_id,
                        datasetId=dataset['datasetReference']['datasetId'],
                        pageToken=table_page_token).execute()
                    for table in tresponse['tables']:
                        table_body = {
                            "labels": {
                                gcp.get_name_tag():
                                table['tableReference']['tableId'].replace(
                                    ".", "_"),
                                gcp.get_loc_tag(): location,
                            }
                        }
                        self.bigquery.tables().patch(
                            projectId=project_id,
                            body=table_body,
                            datasetId=dataset['datasetReference'][
                                'datasetId'],
                            tableId=table['tableReference'][
                                'tableId']).execute()
                        if 'nextPageToken' in tresponse:
                            table_page_token = tresponse['nextPageToken']
                        else:
                            table_more_results = False
