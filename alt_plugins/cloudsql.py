import logging

from google.auth import app_engine
from googleapiclient import discovery, errors

from pluginbase import Plugin

SCOPES = ['https://www.googleapis.com/auth/sqlservice.admin']

CREDENTIALS = app_engine.Credentials(scopes=SCOPES)


class CloudSql(Plugin):

    def __init__(self):
        Plugin.__init__(self)
        self.sqladmin = discovery.build(
            'sqladmin', 'v1beta4', credentials=CREDENTIALS)
        self.batch = self.sqladmin.new_batch_http_request(
            callback=self.batch_callback)


    def register_signals(self):
        logging.debug("Cloud SQL class created and registering signals")


    def _get_name(self, gcp_object):
        try:
            name = gcp_object['name']
            name = name.replace(".", "_").lower()[:62]
        except KeyError as e:
            logging.error(e)
            return None
        return name


    def _get_region(self, gcp_object):
        try:
            region = gcp_object['region']
            region = region.lower()
        except KeyError as e:
            logging.error(e)
            return None
        return region


    def api_name(self):
        return "sqladmin.googleapis.com"


    def method_names(self):
        return ["cloudsql.instances.create"]


    def get_instance(self, project_id, name):
        try:
            result = self.sqladmin.instances().get(
                project=project_id,
                instance=name).execute()
        except errors.HttpError as e:
            logging.error(e)
            return None
        return result


    def get_gcp_object(self, data):
        try:
            if 'response' not in data['protoPayload']:
                return None
            ind = data['resource']['labels']['database_id'].rfind(':')
            instance = data['resource']['labels']['database_id'][ind + 1:]
            instance = self.get_instance(
                data['resource']['labels']['project_id'], instance)

            return instance
        except Exception as e:
            logging.error(e)
            return None


    def do_label(self, project_id):
        page_token = None
        more_results = True
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
                self.label_one(database_instance, project_id)
            if 'nextPageToken' in response:
                page_token = response['nextPageToken']
            else:
                more_results = False


    def label_one(self, gcp_object, project_id):
        labels = dict()
        labels['labels'] = self._gen_labels(gcp_object)
        try:
            database_instance_body = dict()
            database_instance_body['settings'] = {}
            database_instance_body['settings']['userLabels'] = labels['labels']
            self.sqladmin.instances().patch(
                project=project_id, body=database_instance_body,
                instance=gcp_object['name']).execute()
        except Exception as e:
            logging.error(e)
        return 'ok', 200
