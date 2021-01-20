import logging

from googleapiclient import errors

from gce_base.gce_zonal_base import GceZonalBase
from util import gcp_utils


class Instances(GceZonalBase):
    def _get_instance_type(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            machine_type = gcp_object["machineType"]
            ind = machine_type.rfind("/")
            machine_type = machine_type[ind + 1:]
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
            try:
                result = (
                    self._google_client.instances()
                        .list(
                        project=project_id,
                        zone=zone,
                        filter=self._filter_already_labeled,
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
            except errors.HttpError as e:
                logging.exception(e)

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

    def do_label(self, project_id):
        for zone in self._all_zones(project_id):
            instances = self.__list_instances(project_id, zone)
            for instance in instances:
                self.label_one(instance, project_id)
        if self.counter > 0:
            self.do_batch()
        return "OK", 200

    def get_gcp_object(self, data):
        try:
            inst = data["protoPayload"]["resourceName"]
            ind = inst.rfind("/")
            inst = inst[ind + 1:]
            lab = data["resource"]["labels"]
            instance = self.__get_instance(
                lab["project_id"], data["resource"]["labels"]["zone"], inst
            )
            return instance
        except Exception as e:
            logging.exception(e)
            return None

    def label_one(self, gcp_object, project_id):
        labels = self._build_labels(gcp_object, project_id)
        if labels is None:
            return

        try:
            zone = self._get_zone(gcp_object)
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
            if self.counter == 1000:
                self.do_batch()

        except errors.HttpError as e:
            logging.exception(e)
            return "Error", 500

        return "OK", 200
