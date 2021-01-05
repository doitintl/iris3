import logging
import uuid

from google.auth import app_engine
from googleapiclient import discovery, errors

import util.gcp_utils
import util.gcp_utils
from pluginbase import Plugin

SCOPES = ['https://www.googleapis.com/auth/cloud-platform']

CREDENTIALS = app_engine.Credentials(scopes=SCOPES)


class GceDisks(Plugin):

    def __init__(self):
        Plugin.__init__(self)
        self.compute = discovery.build(
            'compute', 'v1', credentials=CREDENTIALS)
        self.batch = self.compute.new_batch_http_request(
            callback=self.batch_callback)

    def register_signals(self):
        logging.debug("GCE Disks class created and registering signals")

    def _get_name(self, gcp_object):
        try:
            name = gcp_object['name']
            name = name.replace(".", "_").lower()[:62]
        except KeyError as e:
            logging.error(e)
            return None
        return name

    def _get_zone(self, gcp_object):
        try:
            zone = gcp_object['zone']
            ind = zone.rfind('/')
            zone = zone[ind + 1:]
            zone = zone.lower()
        except KeyError as e:
            logging.error(e)
            return None
        return zone

    def _get_region(self, gcp_object):
        try:
            zone = gcp_object['zone']
            ind = zone.rfind('/')
            zone = zone[ind + 1:]
            zone = zone.lower()
            region = util.gcp_utils.region_from_zone(zone).lower()
        except KeyError as e:
            logging.error(e)
            return None
        return region

    def api_name(self):
        return "compute.googleapis.com"

    def method_names(self):
        return ["v1.compute.disks.insert"]

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
        List all instances in zone with the requested labels
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
                disk=name).execute()
        except errors.HttpError as e:
            logging.error(e)
            return None
        return result

    def do_label(self, project_id):
        for zone in self.get_zones(project_id):
            disks = self.list_disks(project_id, zone)
            for disk in disks:
                self.label_one(disk, project_id)
        if self.counter > 0:
            self.do_batch()
        return 'ok', 200

    def get_gcp_object(self, data):
        try:
            disk_name = data['protoPayload']['resourceName']
            ind = disk_name.rfind('/')
            disk_name = disk_name[ind + 1:]
            disk = self.get_disk(data['resource']['labels']['project_id'],
                                 data['resource']['labels']['zone'], disk_name)
            return disk
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
        for k, v in org_labels.items():
            labels['labels'][k] = v
        try:
            zone = gcp_object['zone']
            ind = zone.rfind('/')
            zone = zone[ind + 1:]

            self.batch.add(self.compute.disks().setLabels(
                project=project_id,
                zone=zone,
                resource=gcp_object['name'],
                body=labels), request_id=uuid.uuid4())
            self.counter = self.counter + 1
            if self.counter == 1000:
                self.do_batch()

        except Exception as e:
            logging.error(e)
        return 'ok', 200
