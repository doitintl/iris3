import logging

from google.auth import app_engine
from googleapiclient import discovery, errors

from pluginbase import Plugin
from utils import gcp

SCOPES = ['https://www.googleapis.com/auth/cloud-platform']

CREDENTIALS = app_engine.Credentials(scopes=SCOPES)


class GceDisks(Plugin):

    def register_signals(self):
        self.compute = discovery.build(
            'compute', 'v1', credentials=CREDENTIALS)
        logging.debug("GCE class created and registering signals")


    def api_name(self):
        return "compute.googleapis.com"

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
        for zone in response['items']:
            zones.append(zone['description'])
        return zones


    def list_disks(self, project_id, zone):
        """
        List all instances in zone with the requested tags
        Args:
            zone: zone
            project_id: project id
        Returns:
        """

        disks = []
        page_token = None
        more_results = True
        while more_results:
            try:
                result = self.compute.disks().list(
                    project=project_id, zone=zone,
                    filter='-labels.iris_name:*',
                    pageToken=page_token).execute()
                if 'items' in result:
                    disks = disks + result['items']
                if 'nextPageToken' in result:
                    page_token = result['nextPageToken']
                else:
                    more_results = False
            except errors.HttpError as e:
                logging.error(e)

        return disks


    def get_disk(self, project_id, zone, name):
        """
       get an instance
        Args:
            zone: zone
            project_id: project id
            name: instance name
        Returns:
        """

        try:
            result = self.compute.disks().get(
                project=project_id, zone=zone,
                instance=name).execute()
        except errors.HttpError as e:
            logging.error(e)
            return None
        return result


    def do_tag(self, project_id):
        for zone in self.get_zones(project_id):
            disks = self.list_disks(project_id, zone)
            for disk in disks:
                self.tag_one(project_id, zone, disk)
        return 'ok', 200


    def tag_one(self, project_id, zone, disk):
        try:
            org_labels = {}
            org_labels = disk['labels']
        except KeyError:
            pass
        labels = {
            'labelFingerprint': disk.get('labelFingerprint', '')
        }
        labels['labels'] = {}
        labels['labels'][gcp.get_name_tag()] = disk[
            'name'].replace(".",
                            "_").lower()[:62]
        labels['labels'][gcp.get_zone_tag()] = zone.lower()
        labels['labels'][gcp.get_region_tag()] = gcp.region_from_zone(
            zone).lower()
        for k, v in org_labels.items():
            labels['labels'][k] = v
        try:
            request = self.compute.disks().setLabels(
                project=project_id,
                zone=zone,
                resource=disk['name'],
                body=labels)
            request.execute()
        except Exception as e:
            logging.error(e)
        return 'ok', 200
