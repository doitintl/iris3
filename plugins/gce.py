import logging

from google.auth import app_engine
from googleapiclient import discovery, errors

from pluginbase import Plugin
from utils import gcp, utils

SCOPES = ['https://www.googleapis.com/auth/cloud-platform']

CREDENTIALS = app_engine.Credentials(scopes=SCOPES)


class Gce(Plugin):

    def __init__(self):
        Plugin.__init__(self)
        self.compute = discovery.build(
            'compute', 'v1', credentials=CREDENTIALS)
        self.batch = self.compute.new_batch_http_request(
            callback=self.batch_callback)


    def register_signals(self):
        logging.debug("GCE class created and registering signals")


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
            region = gcp.region_from_zone(zone).lower()
        except KeyError as e:
            logging.error(e)
            return None
        return region

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


    def methodsNames(self):
        return ["compute.instances.insert"]


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
        """
       get an instance
        Args:
            zone: zone
            project_id: project id
            name: instance name
        Returns:
        """

        try:
            result = self.compute.instances().get(
                project=project_id, zone=zone,
                instance=name).execute()
        except errors.HttpError as e:
            logging.error(e)
            return None
        return result


    def do_tag(self, project_id):
        for zone in self.get_zones(project_id):
            instances = self.list_instances(project_id, zone)
            for instance in instances:
                self.tag_one(instance, project_id)
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


    def tag_one(self, gcp_object, project_id):
        try:
            org_labels = {}
            org_labels = gcp_object['labels']
        except KeyError:
            pass
        labels = dict(
            [('labelFingerprint', gcp_object.get('labelFingerprint', ''))])
        labels['labels'] = self.gen_labels(gcp_object)
        for k, v in org_labels.items():
            labels['labels'][k] = v
        try:
            zone = gcp_object['zone']
            ind = zone.rfind('/')
            zone = zone[ind + 1:]
            self.batch.add(self.compute.instances().setLabels(
                project=project_id,
                zone=zone,
                instance=gcp_object['name'],
                body=labels), request_id=utils.get_uuid())
            self.counter = self.counter + 1
            if self.counter == 1000:
                self.do_batch()
        except errors.HttpError as e:
            logging.error(e)
        return 'ok', 200
