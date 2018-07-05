import logging

from google.auth import app_engine
from googleapiclient import discovery, errors

from pluginbase import Plugin
from utils import gcp

SCOPES = ['https://www.googleapis.com/auth/cloud-platform']

CREDENTIALS = app_engine.Credentials(scopes=SCOPES)


def batch_callback(request_id, response, exception):
    if exception is not None:
        logging.error(
            'Error instance table {0}: {1}'.format(request_id,
                                                   exception))


class Gce(Plugin):

    def register_signals(self):
        self.compute = discovery.build(
            'compute', 'v1', credentials=CREDENTIALS)
        logging.debug("GCE class created and registering signals")
        self.batch = self.compute.new_batch_http_request(
            callback=batch_callback)
        self.counter = 0


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
                self.tag_one(project_id, zone, instance)
        if self.counter > 0:
            self.batch.execute()
        return 'ok', 200


    def tag_one(self, project_id, zone, instance):
        try:
            org_labels = {}
            org_labels = instance['labels']
        except KeyError:
            pass
        labels = {
            'labelFingerprint': instance.get('labelFingerprint', '')
        }
        labels['labels'] = {}
        labels['labels'][gcp.get_name_tag()] = instance[
                                                   'name'].replace(".",
                                                                   "_").lower()[
                                               :62]
        labels['labels'][gcp.get_zone_tag()] = zone.lower()
        labels['labels'][gcp.get_region_tag()] = gcp.region_from_zone(
            zone).lower()
        for k, v in org_labels.items():
            labels['labels'][k] = v
        try:
            self.batch.add(self.compute.instances().setLabels(
                project=project_id,
                zone=zone,
                instance=instance['name'],
                body=labels), request_id=zone + instance[
                'name'])
            self.counter = self.counter + 1
            if self.counter == 1000:
                self.batch.execute()
                self.counter = 0
        except errors.HttpError as e:
            logging.error(e)
        return 'ok', 200
