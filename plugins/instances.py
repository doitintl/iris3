import logging
from functools import lru_cache
from typing import Dict, Optional, List, Any

import proto
from google.cloud import compute_v1 as compute_cloudclient
from googleapiclient import errors

from gce_base.gce_zonal_base import GceZonalBase
from util import gcp_utils
from util.gcp_utils import cloudclient_pb_obj_to_dict
from util.utils import log_time
from util.utils import timing


class Instances(GceZonalBase):
    @classmethod
    @lru_cache(maxsize=1)
    def _cloudclient(cls):
        return compute_cloudclient.InstancesClient()

    def _gcp_instance_type(self, gcp_object: dict):
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

    def __list_instances(self, project_id, zone) -> List[Dict]:
        # TODO could make this lazy
        page_result = compute_cloudclient.ListInstancesRequest(
            project=project_id, zone=zone
        )
        return self._list_resources_as_dicts(page_result)

    def __get_instance(self, project_id, zone, name) -> Optional[Dict]:
        try:
            request = compute_cloudclient.GetInstanceRequest(
                project=project_id, zone=zone, instance=name
            )

            return self._get_resource_as_dict(request)
        except errors.HttpError as e:
            logging.exception(e)
            return None

    def _get_resource_as_dict(self, request: proto.Message) -> Dict[str, Any]:
        inst = self._cloudclient().get(request)
        return cloudclient_pb_obj_to_dict(inst)

    def label_all(self, project_id):
        with timing(f"label_all(Instance) in {project_id}"):
            zones = self._all_zones()
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
            inst = inst[ind + 1:]
            labels = log_data["resource"]["labels"]["project_id"]
            zone = log_data["resource"]["labels"]["zone"]
            instance = self.__get_instance(labels, zone, inst)
            return instance
        except Exception as e:
            logging.exception("get_gcp_object", exc_info=e)
            return None

    @log_time
    def label_resource(self, gcp_object, project_id):
        self._all_zones()
        labels = self._build_labels(gcp_object, project_id)
        if labels is None:
            return

        zone = self._gcp_zone(gcp_object)

        self._batch.add(
            self._google_api_client()
                .instances()
                .setLabels(
                project=project_id,
                zone=zone,
                instance=gcp_object["name"],
                body=labels,
            ),
            request_id=gcp_utils.generate_uuid(),
        )
        # Could do this, but that apparently that does not support batching
        #  compute_v1.SetLabelsInstanceRequest(project=project_id, zone=zone, instance=name, labels=labels)

        self.counter += 1
        if self.counter >= self._BATCH_SIZE:
            self.do_batch()
