""" Taging BQ tabels and datasets."""
import logging
import traceback
import uuid

from google.auth import app_engine
from googleapiclient import discovery, errors
from ratelimit import limits, sleep_and_retry

from pluginbase import Plugin

SCOPES = ['https://www.googleapis.com/auth/bigquery']

CREDENTIALS = app_engine.Credentials(scopes=SCOPES)


class BigQuery(Plugin):

    def __init__(self):
        Plugin.__init__(self)
        self.bigquery = discovery.build(
            'bigquery', 'v2', credentials=CREDENTIALS)
        self.batch = self.bigquery.new_batch_http_request(
            callback=self.batch_callback)

    def register_signals(self):
        """
           Register with the plugin manager.
        """
        logging.debug("BigQuery class created and registering signals")

    def api_name(self):
        return "bigquery-json.googleapis.com"

    def method_names(self):
        return ["datasetservice.insert", "tableservice.insert"]

    def _get_name(self, gcp_object):
        try:
            if gcp_object['kind'] == "bigquery#dataset":
                name = gcp_object['datasetReference']['datasetId']
                ind = name.rfind(':')
                name = name[ind + 1:]
            else:
                name = gcp_object['tableReference']['tableId']
                ind = name.rfind(':')
                name = name[ind + 1:]
            name = name.replace(".", "_").lower()[:62]
        except KeyError as e:
            logging.error(e)
            return None
        return name

    def _get_location(self, gcp_object):
        try:
            location = gcp_object['location']
            location = location.lower()
        except KeyError as e:
            logging.error(e)
            return None
        return location

    def get_dataset(self, project_id, name):
        try:
            result = self.bigquery.datasets().get(
                projectId=project_id,
                datasetId=name).execute()
        except errors.HttpError as e:
            logging.error(e)
            return None
        return result

    def get_table(self, project_id, dataset, table):
        try:
            result = self.bigquery.tables().get(
                projectId=project_id,
                datasetId=dataset, tableId=table).execute()
        except errors.HttpError as e:
            logging.error(e)
            return None
        return result

    def get_gcp_object(self, data):
        try:
            datasetid = \
                data['protoPayload']['serviceData']['datasetInsertRequest'][
                    'resource']['datasetName']['datasetId']
            projectid = \
                data['protoPayload']['serviceData']['datasetInsertRequest'][
                    'resource']['datasetName']['projectId']
            dataset = self.get_dataset(projectid, datasetid)
            return dataset
        except Exception:
            pass
        try:
            tableid = \
                data['protoPayload']['serviceData']['tableInsertRequest'][
                    'resource']['tableName']['tableId']
            projectid = \
                data['protoPayload']['serviceData']['tableInsertRequest'][
                    'resource']['tableName']['projectId']
            datasetid = \
                data['protoPayload']['serviceData']['tableInsertRequest'][
                    'resource']['tableName']['datasetId']
            table = self.get_table(projectid, datasetid, tableid)
            return table
        except Exception as e:
            logging.error(e)
            print((traceback.format_exc()))

        return None

    def do_label(self, project_id):
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
                    self.tag_one_dataset(dataset)
                    table_page_token = None
                    table_more_results = True
                    while table_more_results:
                        tresponse = self.bigquery.tables().list(
                            projectId=project_id,
                            datasetId=dataset['datasetReference']['datasetId'],
                            pageToken=table_page_token).execute()
                        if 'tables' in tresponse:
                            for t in tresponse['tables']:
                                t['location'] = dataset['location']
                                self.tag_one_table(t)
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
    @limits(calls=35, period=60)
    def tag_one_dataset(self, gcp_object):
        labels = dict()
        labels['labels'] = self._gen_labels(gcp_object)
        try:
            self.bigquery.datasets().patch(
                projectId=gcp_object['datasetReference']['projectId'],
                body=labels,
                datasetId=gcp_object['datasetReference'][
                    'datasetId']).execute()
        except Exception as e:
            logging.error(e)

    @sleep_and_retry
    @limits(calls=35, period=60)
    def tag_one_table(self, gcp_object):
        labels = dict()
        labels['labels'] = self._gen_labels(gcp_object)
        try:

            self.batch.add(self.bigquery.tables().patch(
                projectId=gcp_object['tableReference']['projectId'],
                body=labels,
                datasetId=gcp_object['tableReference']['datasetId'],
                tableId=gcp_object['tableReference'][
                    'tableId']), request_id=uuid.uuid4())
            self.counter = self.counter + 1
            if self.counter == 1000:
                self.do_batch()
        except Exception as e:
            logging.error(e)
        if self.counter > 0:
            self.do_batch()

    def label_one(self, gcp_object, project_id):
        try:
            if gcp_object['kind'] == "bigquery#dataset":
                self.tag_one_dataset(gcp_object)
            else:
                self.tag_one_table(gcp_object)
        except Exception as e:
            logging.error(e)
