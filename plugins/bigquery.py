""" Taging BQ tabels and datasets."""
import logging

from google.auth import app_engine
from googleapiclient import discovery, errors
from ratelimit import limits, sleep_and_retry

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


    def api_name(self):
        return "bigquery-json.googleapis.com"


    def do_tag(self, project_id):
        """
        tag tables and data sets
        :param project_id: project id
        """
        page_token = None
        more_results = True
        while more_results:
            try:
                response = self.bigquery.datasets().list(
                    projectId=project_id, pageToken=page_token).execute()
            except errors.HttpError as e:
                logging.error(e)
                return
            if 'datasets' in response:
                for dataset in response['datasets']:
                    location = dataset['location'].lower()
                    self.tag_one_dataset(dataset, project_id, location)
                    table_page_token = None
                    table_more_results = True
                    while table_more_results:
                        tresponse = self.bigquery.tables().list(
                            projectId=project_id,
                            datasetId=dataset['datasetReference']['datasetId'],
                            pageToken=table_page_token).execute()
                        if 'tables' in tresponse:
                            self.tag_one_table(tresponse, project_id, location,
                                               dataset['datasetReference'][
                                                   'datasetId'])
                        if 'nextPageToken' in tresponse:
                            table_page_token = tresponse['nextPageToken']
                            table_more_results = True
                        else:
                            table_more_results = False
            if 'nextPageToken' in response:
                page_token = response['nextPageToken']
            else:
                more_results = False


    @sleep_and_retry
    @limits(calls=50, period=1)
    def tag_one_dataset(self, dataset, project_id, location):
        ds_body = {
            "labels": {
                gcp.get_loc_tag(): location,
                gcp.get_name_tag(): dataset['datasetReference'][
                                        'datasetId'].replace(".",
                                                             "_").lower()[:62],
            }
        }
        try:
            self.bigquery.datasets().patch(
                projectId=project_id,
                body=ds_body,
                datasetId=dataset['datasetReference'][
                    'datasetId']).execute()
        except Exception as e:
            logging.error(e)


    @sleep_and_retry
    @limits(calls=50, period=1)
    def tag_one_table(self, tresponse, project_id, location, dataset_id):
        def batch_callback(request_id, response, exception):
            if exception is not None:
                logging.error(
                    'Error patching table {0}: {1}'.format(request_id,
                                                           exception))


        batch = self.bigquery.new_batch_http_request(callback=batch_callback)
        counter = 0
        for table in tresponse['tables']:
            table_body = {
                "labels": {
                    gcp.get_name_tag():
                        table['tableReference'][
                            'tableId'].replace(
                            ".", "_").lower()[:62],
                    gcp.get_loc_tag(): location,
                }
            }
            try:
                batch.add(self.bigquery.tables().patch(
                    projectId=project_id,
                    body=table_body,
                    datasetId=dataset_id,
                    tableId=table['tableReference'][
                        'tableId']), request_id=table['tableReference'][
                                                    'tableId'].replace(
                    ".", "_").lower())
                counter = counter + 1
                if counter == 1000:
                    batch.execute()
                    counter = 0
            except Exception as e:
                logging.error(e)
                logging.error(table_body)
        if counter > 0:
            batch.execute()
