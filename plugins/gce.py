import logging

from google.auth import app_engine
from googleapiclient import discovery

from pluginbase import Plugin
from utils import gcp

SCOPES = ['https://www.googleapis.com/auth/cloud-platform']

CREDENTIALS = app_engine.Credentials(scopes=SCOPES)


class Gce(Plugin):

    def register_signals(self):
        self.compute = discovery.build(
            'compute', 'v1', credentials=CREDENTIALS)
        logging.debug("GCE class created and registering signals")

    def get_zones(self, projectid):
        """
        Get all available zones.
        Args:
            project_id: project id
        :return: all regions
        """

        request = self.compute.zones().list(project=projectid)

        response = request.execute()
        zones = []
        for region in response['items']:
            zones.append(region['description'])
        return zones

    def list_instances(self, project_id, zone):
        """
        List all instances in zone with the requested tags
        Args:
            zone: zone
            project_id: project id
        Returns:
        """

        instances = []
        page_token = None
        more_results = True
        while more_results:
            result = self.compute.instances().list(
                project=project_id, zone=zone, pageToken=page_token).execute()
            if 'items' in result:
                instances = instances + result['items']
            if 'nextPageToken' in result:
                page_token = result['nextPageToken']
            else:
                more_results = False
        return instances

    def do_tag(self, project_id):
        for zone in self.get_zones(project_id):
            instances = self.list_instances(project_id, zone)
            for instance in instances:
                labels = {
                    "labels": {
                        gcp.get_name_tag(): instance['name'].replace(".", "_")
                    },
                    'labelFingerprint': instance.get('labelFingerprint', '')
                }
                request = self.compute.instances().setLabels(
                    project=project_id,
                    zone=zone,
                    instance=instance['name'],
                    body=labels)
                request.execute()
        return 'ok', 200
