import logging

from googleapiclient import discovery, errors

import util.gcp_utils
from pluginbase import Plugin
from util import gcp_utils


class Bigtable(Plugin):
    google_client = discovery.build('bigtableadmin', 'v2')

    def __init__(self):
        super().__init__()

        self.batch = self.google_client.new_batch_http_request(
            callback=self.batch_callback)

    def api_name(self):
        return 'bigtableadmin.googleapis.com'

    def method_names(self):
        return ['google.bigtable.admin.v2.BigtableInstanceAdmin.CreateInstance']

    def _get_name(self, gcp_object):
        """Method dynamically called in _gen_labels, so don't change name"""
        try:
            name = gcp_object['name']
            index = name.rfind('/')
            name = name[index + 1:]
            name = name.replace('.', '_').lower()[:62]
            return name
        except KeyError as e:
            logging.exception(e)
            return None

    def _get_zone(self, gcp_object):
        """Method dynamically called in _gen_labels, so don't change name"""
        try:
            location = self.__get_location(gcp_object, gcp_object['project_id'])
            return location
        except KeyError as e:
            logging.error(e)
            return None

    def _get_region(self, gcp_object):
        """Method dynamically called in _gen_labels, so don't change name"""
        try:
            zone = self.__get_location(gcp_object, gcp_object['project_id'])
            region = util.gcp_utils.region_from_zone(zone).lower()
            return region
        except KeyError as e:
            logging.error(e)
            return None

    def _get_cluster(self, project_id, name):
        """Method dynamically called in _gen_labels, so don't change name"""
        try:
            result = self.google_client.projects().instances().clusters().list(
                parent="projects/" + project_id + "/instances/" + name).execute()

            return result
        except errors.HttpError as e:
            logging.error(e)
            return None

    def __get_location(self, gcp_object, project_id):
        instance = gcp_object['displayName']
        result = self._get_cluster(project_id, instance)
        loc = result['clusters'][0]['location']
        ind = loc.rfind('/')
        return loc[ind + 1:]

    def __get_instance(self, project_id, name):
        try:
            result = self.google_client.projects().instances().get(
                name="projects/" + project_id + "/instances/" + name).execute()
            return result
        except errors.HttpError as e:
            logging.error(e)
            return None

    def get_gcp_object(self, data):
        try:
            instance = self.__get_instance(
                data['resource']['labels']['project_id'],
                data['protoPayload']['request']['instanceId'])
            return instance
        except Exception as e:
            logging.error(e)
            return None

    def do_label(self, project_id):
        page_token = None
        more_results = True
        while more_results:
            try:
                result = self.google_client.projects().instances().list(
                    parent="projects/" + project_id,
                    pageToken=page_token).execute()
            except errors.HttpError as e:
                logging.error(e)
                return
            if 'instances' in result:
                for inst in result['instances']:
                    self.label_one(inst, project_id)
            if 'nextPageToken' in result:
                page_token = result['nextPageToken']
            else:
                more_results = False
            if self.counter > 0:
                self.do_batch()

    def label_one(self, gcp_object, project_id):
        labels = dict()
        gcp_object['project_id'] = project_id  # TODO Why was this line here? Can I remove it (and 2 lines down?)
        labels['labels'] = self._gen_labels(gcp_object)
        gcp_object.pop('project_id', None)
        if 'labels' not in gcp_object:
            gcp_object['labels'] = {}

        for key, val in labels['labels'].items():
            gcp_object['labels'][key] = val

        try:

            self.batch.add(
                self.google_client.projects().instances().partialUpdateInstance(
                    name=gcp_object['name'],
                    body=gcp_object,
                    updateMask='labels'),
                request_id=gcp_utils.generate_uuid())
            self.counter += 1
            if self.counter == 1000:
                self.do_batch()
        except Exception as e:
            logging.exception(e)
        return 'OK', 200
