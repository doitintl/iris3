import logging
import uuid

from google.auth import app_engine
from googleapiclient import discovery, errors

from pluginbase import Plugin

SCOPES = ['https://www.googleapis.com/auth/cloud-platform']

CREDENTIALS = app_engine.Credentials(scopes=SCOPES)


class GceSnapshots(Plugin):

    def __init__(self):
        Plugin.__init__(self)
        self.compute = discovery.build(
            'compute', 'v1', credentials=CREDENTIALS)
        self.batch = self.compute.new_batch_http_request(
            callback=self.batch_callback)


    def register_signals(self):
        logging.debug("GCE Snapshots class created and registering signals")


    def _get_name(self, gcp_object):
        try:
            name = gcp_object['name']
            name = name.replace(".", "_").lower()[:62]
        except KeyError as e:
            logging.error(e)
            return None
        return name


    def api_name(self):
        return "compute.googleapis.com"


    def method_names(self):
        return ["v1.compute.disks.createSnapshot"]


    def list_snapshots(self, project_id):
        """
        List all instances in zone with the requested labels
        Args:
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
            project_id: project id
            name: instance name
        Returns:
        """

        try:
            result = self.compute.snapshots().get(
                project=project_id,
                snapshot=name).execute()
        except errors.HttpError as e:
            logging.error(e)
            return None
        return result


    def do_label(self, project_id):
        snapshots = self.list_snapshots(project_id)
        for snapshot in snapshots:
            self.label_one(snapshot, project_id)
        if self.counter > 0:
            self.do_batch()
        return 'ok', 200


    def get_gcp_object(self, data):
        try:
            if 'response' not in data['protoPayload']:
                return None
            snap_name = data['protoPayload']['request']['name']
            snapshot = self.get_snapshot(
                data['resource']['labels']['project_id'], snap_name)
            return snapshot
        except Exception as e:
            logging.error(e)
            return None


    def label_one(self, gcp_object, project_id):
        try:
            org_labels = {}
            org_labels = gcp_object['labels']
        except KeyError:
            pass

        labels = dict(
            [('labelFingerprint', gcp_object.get('labelFingerprint', ''))])
        labels['labels'] = self._gen_labels(gcp_object)
        for k, v in list(org_labels.items()):
            labels['labels'][k] = v
        try:

            self.batch.add(self.compute.snapshots().setLabels(
                project=project_id,
                resource=gcp_object['name'],
                body=labels), request_id= uuid.uuid4())
            self.counter = self.counter + 1
            if self.counter == 1000:
                self.do_batch()
        except Exception as e:
            logging.error(e)
        return 'ok', 200
