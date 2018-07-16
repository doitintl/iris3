import logging

from google.auth import app_engine
from googleapiclient import discovery, errors

from pluginbase import Plugin
from utils import gcp, utils

SCOPES = ['https://www.googleapis.com/auth/bigtable.admin']

CREDENTIALS = app_engine.Credentials(scopes=SCOPES)


class BigTable(Plugin):

    def __init__(self):
        Plugin.__init__(self)
        self.bigtable = discovery.build(
            'bigtableadmin', 'v2', credentials=CREDENTIALS)
        self.batch = self.bigtable.new_batch_http_request(
            callback=self.batch_callback)


    def register_signals(self):
        """
        Register with the plugin manager.
        """
        logging.debug("BigTable class created and registering signals")


    def api_name(self):
        return "bigtableadmin.googleapis.com"


    def methodsNames(self):
        return [
            "google.bigtable.admin.v2.BigtableInstanceAdmin.CreateInstance"]


    def _get_name(self, gcp_object):
        try:
            name = gcp_object['name']
            ind = name.rfind('/')
            name = name[ind + 1:]
            name = name.replace(".", "_").lower()[:62]
        except KeyError as e:
            logging.error(e)
            return None
        return name


    def _get_zone(self, gcp_object):
        try:
            location = self.get_location(gcp_object, gcp_object['project_id'])
        except KeyError as e:
            logging.error(e)
            return None
        return location


    def _get_region(self, gcp_object):
        try:
            zone = self.get_location(gcp_object, gcp_object['project_id'])
            region = gcp.region_from_zone(zone).lower()
        except KeyError as e:
            logging.error(e)
            return None
        return region


    def get_location(self, gcp_object, project_id):
        instance = gcp_object['displayName']
        result = self._get_cluster(project_id, instance)
        loc = result['clusters'][0]['location']
        ind = loc.rfind('/')
        return loc[ind + 1:]


    def get_instance(self, project_id, name):
        try:
            result = self.bigtable.projects().instances().get(
                name="projects/" + project_id + "/instances/" + name).execute()
        except errors.HttpError as e:
            logging.error(e)
            return None
        return result


    def _get_cluster(self, project_id, name):
        try:
            result = self.bigtable.projects().instances().clusters().list(
                parent="projects/" + project_id + "/instances/" +
                       name).execute()
        except errors.HttpError as e:
            logging.error(e)
            return None
        return result


    def get_gcp_object(self, data):
        try:
            instance = self.get_instance(
                data['resource']['labels']['project_id'],
                data['protoPayload']['request']['instanceId'])
            return instance
        except Exception as e:
            logging.error(e)
            return None


    def do_tag(self, project_id):
        page_token = None
        more_results = True
        while more_results:
            try:
                result = self.bigtable.projects().instances().list(
                    parent="projects/" + project_id,
                    pageToken=page_token).execute()
            except errors.HttpError as e:
                logging.error(e)
                return
            if 'instances' in result:
                for inst in result['instances']:
                    self.tag_one(inst, project_id)
            if 'nextPageToken' in result:
                page_token = result['nextPageToken']
            else:
                more_results = False
            if self.counter > 0:
                self.do_batch()


    def tag_one(self, gcp_object, project_id):
        labels = dict()
        gcp_object['project_id'] = project_id
        labels['labels'] = self.gen_labels(gcp_object)
        gcp_object.pop('project_id', None)
        if 'labels' in gcp_object:
            for key, val in labels['labels'].items():
                gcp_object['labels'][key] = val
        else:
            gcp_object['labels'] = {}
            for key, val in labels['labels'].items():
                gcp_object['labels'][key] = val

        try:
            self.batch.add(self.bigtable.projects().instances(
            ).partialUpdateInstance(
                name=gcp_object['name'], body=gcp_object,
                updateMask='labels'), request_id=utils.get_uuid())
            self.counter = self.counter + 1
            if self.counter == 1000:
                self.do_batch()
        except Exception as e:
            logging.error(e)
        return 'ok', 200
