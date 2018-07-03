import logging

from google.auth import app_engine
from googleapiclient import discovery, errors

from pluginbase import Plugin
from utils import gcp

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
        while more_results:
            result = self.bigtable.projects().instances().list(
                parent="projects/" + project_id,
                pageToken=page_token).execute()
            if 'instances' in result:
                for inst in result['instances']:
                    if 'labels' in inst:
                        inst['labels'].update(
                            {gcp.get_name_tag(): inst['displayName'].lower()})
                    else:
                        inst['labels'] = {
                            gcp.get_name_tag(): inst['displayName'].replace(
                                ".", "_").lower()
                        }
                    try:
                        self.bigtable.projects().instances(
                        ).partialUpdateInstance(
                            name=inst['name'], body=inst,
                            updateMask='labels').execute()
                    except errors.HttpError as e:
                        logging.error(e)
            if 'nextPageToken' in result:
                page_token = result['nextPageToken']
            else:
                more_results = False
