import logging

from google.auth import app_engine
from googleapiclient import discovery, errors

from pluginbase import Plugin
from utils import gcp, utils

SCOPES = ['https://www.googleapis.com/auth/bigtable.admin']

CREDENTIALS = app_engine.Credentials(scopes=SCOPES)


class BigTable(Plugin):

    def register_signals(self):
        """
        Register with the plugin manager.
        """
        self.bigtable = discovery.build(
            'bigtableadmin', 'v2', credentials=CREDENTIALS)
        logging.debug("BigTable class created and registering signals")


    def api_name(self):
        return "bigtableadmin.googleapis.com"


    def do_tag(self, project_id):
        page_token = None
        more_results = True
        def batch_callback(request_id, response, exception):
            if exception is not None:
                logging.error(
                    'Error patching instance {0}: {1}'.format(request_id,
                                                           exception))

        batch = self.bigtable.new_batch_http_request(callback=batch_callback)
        counter = 0
        while more_results:
            try:
                result = self.bigtable.projects().instances().list(
                    parent="projects/" + project_id,
                    pageToken=page_token).execute()
            except errors.HttpError as e:
                logging.error(e)
                return
            if 'instances' in result:
                for inst in result['instances']:
                    if 'labels' in inst:
                        inst['labels'].update(
                            {gcp.get_name_tag(): inst['displayName'].lower()[
                                                 :62]})
                    else:
                        inst['labels'] = {
                            gcp.get_name_tag(): inst['displayName'].replace(
                                ".", "_").lower()[:62]
                        }
                    try:
                        batch.add(self.bigtable.projects().instances(
                        ).partialUpdateInstance(
                            name=inst['name'], body=inst,
                            updateMask='labels'), request_id=utils.get_uuid())
                        counter = counter + 1
                        if counter == 1000:
                            batch.execute()
                            counter = 0
                    except Exception as e:
                        logging.error(e)
            if 'nextPageToken' in result:
                page_token = result['nextPageToken']
            else:
                more_results = False
            if counter > 0:
                batch.execute()
