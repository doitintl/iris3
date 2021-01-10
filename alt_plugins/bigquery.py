"""
Labeling BQ tables and datasets.
"""
import logging

from googleapiclient import discovery, errors
from ratelimit import limits, sleep_and_retry

from pluginbase import Plugin
from util import gcp_utils


# TODO Test this plugin in the Cloud
class Bigquery(Plugin):
    google_client = discovery.build('bigquery', 'v2')

    def __init__(self):
        super().__init__()

        self.batch = self.google_client.new_batch_http_request(
            callback=self.batch_callback)

    def api_name(self):
        return "bigquery-json.googleapis.com"

    def method_names(self):
        return ["datasetservice.insert", "tableservice.insert"]

    def _get_name(self, gcp_object):
        """Method dynamically called in _gen_labels, so don't change name"""
        try:
            if gcp_object['kind'] == "bigquery#dataset":
                name = gcp_object['datasetReference']['datasetId']
            else:
                name = gcp_object['tableReference']['tableId']
            index = name.rfind(':')
            name = name[index + 1:]
            name = name.replace('.', '_').lower()[:62]
            return name
        except KeyError as e:
            logging.exception(e)
            return None

    def _get_location(self, gcp_object):
        """Method dynamically called in _gen_labels, so don't change name"""
        try:
            location = gcp_object['location']
            location = location.lower()
            return location
        except KeyError as e:
            logging.exception(e)
            return None

    def __get_dataset(self, project_id, name):
        try:
            result = self.google_client.datasets().get(
                projectId=project_id,
                datasetId=name).execute()
            return result
        except errors.HttpError as e:
            logging.error(e)
            return None

    def __get_table(self, project_id, dataset, table):
        try:
            result = self.google_client.tables().get(
                projectId=project_id,
                datasetId=dataset, tableId=table).execute()
            return result
        except errors.HttpError as e:
            logging.error(e)
            return None

    def get_gcp_object(self, data):
        try:
            dataset_name = data['protoPayload']['serviceData']['datasetInsertRequest']['resource']['datasetName']
            datasetid = dataset_name['datasetId']
            projectid = dataset_name['projectId']
            dataset = self.__get_dataset(projectid, datasetid)
            return dataset
        except Exception:
            # No such dataset; hoping for table
            pass
        try:
            table_name = data['protoPayload']['serviceData']['tableInsertRequest']['resource']['tableName']
            tableid = table_name['tableId']
            projectid = table_name['projectId']
            datasetid = table_name['datasetId']
            table = self.__get_table(projectid, datasetid, tableid)
            return table
        except Exception as e:
            logging.exception(e)
            return None

    def do_label(self, project_id):
        """
        Label both tables and data sets
        """
        page_token = None
        more_results = True
        while more_results:
            try:
                response = self.google_client.datasets().list(
                    projectId=project_id, pageToken=page_token).execute()
            except errors.HttpError as e:
                logging.exception(e)
                return
            if 'datasets' in response:
                for dataset in response['datasets']:
                    self.__label_tables_in_dataset(project_id, dataset)
            if 'nextPageToken' in response:
                page_token = response['nextPageToken']
            else:
                more_results = False

    def __label_tables_in_dataset(self, project_id, dataset):
        self.__label_one_dataset(dataset)
        page_token = None
        more_results = True
        while more_results:
            response = self.google_client.tables().list(
                projectId=project_id,
                datasetId=dataset['datasetReference']['datasetId'],
                pageToken=page_token).execute()
            if 'tables' in response:
                for t in response['tables']:
                    t['location'] = dataset['location']
                    self.__label_one_table(t)
            if 'nextPageToken' in response:
                page_token = response['nextPageToken']
                more_results = True
            else:
                more_results = False

    @sleep_and_retry
    @limits(calls=35, period=60)
    def __label_one_dataset(self, gcp_object):
        labels = {'labels': self._gen_labels(gcp_object)}
        try:
            self.google_client.datasets().patch(
                projectId=gcp_object['datasetReference']['projectId'],
                body=labels,
                datasetId=gcp_object['datasetReference'][
                    'datasetId']).execute()
        except Exception as e:
            logging.exception(e)

    @sleep_and_retry
    @limits(calls=35, period=60)
    def __label_one_table(self, gcp_object):
        labels = {'labels': self._gen_labels(gcp_object)}
        try:

            table_reference = gcp_object['tableReference']
            self.batch.add(self.google_client.tables().patch(
                projectId=table_reference['projectId'],
                body=labels,
                datasetId=table_reference['datasetId'],
                tableId=table_reference['tableId']), request_id=gcp_utils.generate_uuid())
            self.counter += 1
            if self.counter == 1000:
                self.do_batch()
        except Exception as e:
            logging.exception(e)
        if self.counter > 0:
            self.do_batch()

    def label_one(self, gcp_object, project_id):
        try:
            if gcp_object['kind'] == 'bigquery#dataset':
                self.__label_one_dataset(gcp_object)
            else:
                self.__label_one_table(gcp_object)
        except Exception as e:
            logging.error(e)
