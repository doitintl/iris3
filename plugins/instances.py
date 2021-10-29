import logging

from googleapiclient import errors

from gce_base.gce_zonal_base import GceZonalBase
from util import gcp_utils
from util.utils import log_time
from util.utils import timing


class Instances(GceZonalBase):
    def _gcp_instance_type(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            machine_type = gcp_object["machineType"]
            ind = machine_type.rfind("/")
            machine_type = machine_type[ind + 1 :]
            return machine_type
        except KeyError as e:
            logging.exception(e)
            return None

    def method_names(self):
        return ["compute.instances.insert", "compute.instances.start"]

    def __list_instances(self, project_id, zone):
        instances = []
        page_token = None
        more_results = True
        while more_results:
            result = (
                self._google_client.instances()
                .list(
                    project=project_id,
                    zone=zone,
                    pageToken=page_token,
                )
                .execute()
            )
            if "items" in result:
                instances = instances + result["items"]
            if "nextPageToken" in result:
                page_token = result["nextPageToken"]
            else:
                more_results = False

        return instances

    def __get_instance(self, project_id, zone, name):
        try:
            result = (
                self._google_client.instances()
                .get(project=project_id, zone=zone, instance=name)
                .execute()
            )
            return result
        except errors.HttpError as e:
            logging.exception(e)
            return None

    def label_all(self, project_id):
        with timing(f"label_all(Instance) in {project_id}"):
            zones = self._all_zones(project_id)
            with timing(f" label instances in {len(zones)} zones"):
                for zone in zones:
                    instances = self.__list_instances(project_id, zone)
                    for instance in instances:
                        try:
                            self.label_resource(instance, project_id)
                        except Exception as e:
                            logging.exception(e)
            if self.counter > 0:
                self.do_batch()

    def get_gcp_object(self, log_data):
        try:
            inst = log_data["protoPayload"]["resourceName"]
            ind = inst.rfind("/")
            inst = inst[ind + 1 :]
            labels = log_data["resource"]["labels"]["project_id"]
            zone = log_data["resource"]["labels"]["zone"]
            instance = self.__get_instance(labels, zone, inst)
            return instance
        except Exception as e:
            logging.exception(e)
            return None

    @log_time
    def label_resource(self, gcp_object, project_id):
        labels = self._build_labels(gcp_object, project_id)
        if labels is None:
            return

        zone = self._gcp_zone(gcp_object)
        self._batch.add(
            self._google_client.instances().setLabels(
                project=project_id,
                zone=zone,
                instance=gcp_object["name"],
                body=labels,
            ),
            request_id=gcp_utils.generate_uuid(),
        )
        self.counter += 1
        if self.counter >= self._BATCH_SIZE:
            self.do_batch()
