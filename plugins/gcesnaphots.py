import logging

from google.auth import app_engine
from googleapiclient import discovery, errors

from pluginbase import Plugin
from utils import gcp, utils

SCOPES = ['https://www.googleapis.com/auth/cloud-platform']

CREDENTIALS = app_engine.Credentials(scopes=SCOPES)


def batch_callback(request_id, response, exception):
    if exception is not None:
        logging.error(
            'Error patching snapshot {0}: {1}'.format(request_id,
                                                      exception))


class GceSnapshots(Plugin):

    def register_signals(self):
        self.compute = discovery.build(
            'compute', 'v1', credentials=CREDENTIALS)
        logging.debug("GCE class created and registering signals")
        self.batch = self.compute.new_batch_http_request(
            callback=batch_callback)
        self.counter = 0


    def api_name(self):
        return "compute.googleapis.com"


    def list_snapshots(self, project_id):
        """
        List all instances in zone with the requested tags
        Args:
            zone: zone
            project_id: project id
        Returns:
        """

        snapshots = []
        page_token = None
        more_results = True
        while more_results:
            try:
                result = self.compute.snapshots().list(
                    project=project_id,
                    filter='-labels.iris_name:*',
                    pageToken=page_token).execute()
                if 'items' in result:
                    snapshots = snapshots + result['items']
                if 'nextPageToken' in result:
                    page_token = result['nextPageToken']
                else:
                    more_results = False
            except errors.HttpError as e:
                logging.error(e)

        return snapshots


    def get_snapshot(self, project_id, name):
        """
       get an instance
        Args:
            zone: zone
            project_id: project id
            name: instance name
        Returns:
        """

        try:
            result = self.compute.snapshots().get(
                project=project_id,
                resource=name).execute()
        except errors.HttpError as e:
            logging.error(e)
            return None
        return result


    def do_tag(self, project_id):
        snapshots = self.list_snapshots(project_id)
        for snapshot in snapshots:
            self.tag_one(project_id, snapshot)
        if self.counter > 0:
            self.batch.execute()
        return 'ok', 200


    def tag_one(self, project_id, snapshot):
        try:
            org_labels = {}
            org_labels = snapshot['labels']
        except KeyError:
            pass
        labels = {
            'labelFingerprint': snapshot.get('labelFingerprint', '')
        }
        labels['labels'] = {}
        labels['labels'][gcp.get_name_tag()] = snapshot[
                                                   'name'].replace(".",
                                                                   "_").lower()[
                                               :62]
        for k, v in org_labels.items():
            labels['labels'][k] = v
        try:
            self.batch.add(self.compute.snapshots().setLabels(
                project=project_id,
                resource=snapshot['name'],
                body=labels), request_id=utils.get_uuid())
            self.counter = self.counter + 1
            if self.counter == 1000:
                self.batch.execute()
                counter = 0
        except Exception as e:
            logging.error(e)
        return 'ok', 200
