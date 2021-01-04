import logging
import uuid

from googleapiclient import discovery, errors

import utils.gcp_utils
from pluginbase import Plugin
from utils import gcp_utils


class Gce(Plugin):
    compute = discovery.build('compute', 'v1')

    def __init__(self):
        super().__init__()

        self.batch = self.compute.new_batch_http_request(
            callback=self.batch_callback)

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
            index = zone.rfind('/')
            zone = zone[index + 1:]
            zone = zone.lower()
            return zone
        except KeyError as e:
            logging.error(e)
            return None

    def _get_region(self, gcp_object):
        try:
            zone = self._get_zone(gcp_object)
            region = utils.gcp_utils.region_from_zone(zone).lower()
            return region
        except KeyError as e:
            logging.error(e)
            return None

    def _get_instance_type(self, gcp_object):
        try:
            machineType = gcp_object['machineType']
            ind = machineType.rfind('/')
            machineType = machineType[ind + 1:]
        except KeyError as e:
            logging.error(e)
            return None
        return machineType

    def api_name(self):
        return "compute.googleapis.com"

    def method_names(self):
        return ["compute.instances.insert"]

    def get_zones(self, project_id):
        """
        Get all available zones.
        """

        request = self.compute.zones().list(project=project_id)
        response = request.execute()
        zones = [zone['description'] for zone in response['items']]
        return zones

    def list_instances(self, project_id, zone):
        instances = []
        page_token = None
        more_results = True
        while more_results:
            try:
                result = self.compute.instances().list(
                    project=project_id, zone=zone,
                    filter='-labels.iris_name:*',
                    pageToken=page_token).execute()
                if 'items' in result:
                    instances = instances + result['items']
                if 'nextPageToken' in result:
                    page_token = result['nextPageToken']
                else:
                    more_results = False
            except errors.HttpError as e:
                logging.error(e)

        return instances

    def get_instance(self, project_id, zone, name):
        try:
            result = self.compute.instances().get(
                project=project_id, zone=zone, instance=name).execute()
            return result
        except errors.HttpError as e:
            logging.error(e)
            return None

    def do_label(self, project_id, **kwargs):
        filter_zones_or_regions = kwargs.get('zones', []).split(',')
        for zone in self.get_zones(project_id):
            # TODO: Spawn off processing in parallel per-zone
            if not filter_zones_or_regions or any(z in zone for z in filter_zones_or_regions):
                instances = self.list_instances(project_id, zone)
                for instance in instances:
                    self.label_one(instance, project_id)
        if self.counter > 0:
            self.do_batch()
        return 'ok', 200

    def get_gcp_object(self, data):
        try:
            inst = data['protoPayload']['resourceName']
            ind = inst.rfind('/')
            inst = inst[ind + 1:]
            instance = self.get_instance(
                data['resource']['labels']['project_id'],
                data['resource']['labels']['zone'],
                inst)
            return instance
        except Exception as e:
            logging.error(e)
            return None

    def label_one(self, gcp_object, project_id):
        try:
            original_labels = gcp_object['labels']
        except KeyError:
            original_labels = {}

        gen_labels = self._gen_labels(gcp_object)
        all_labels= {**gen_labels, **original_labels}
        labels = {
            'labels': all_labels,
            'labelFingerprint': gcp_object.get('labelFingerprint', '')
        }

        try:
            zone = self._get_zone(gcp_object)

            self.batch.add(self.compute.instances().setLabels(
                project=project_id,
                zone=zone,
                instance=gcp_object['name'],
                body=labels),
                request_id=gcp_utils.generate_uuid())

            self.counter = self.counter + 1
            if self.counter == 1000:
                self.do_batch()

        except errors.HttpError as e:
            logging.error(e)
        return 'ok', 200

