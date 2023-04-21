import logging
import threading
from functools import lru_cache
from typing import Dict, Optional, List

from googleapiclient import errors

from gce_base.gce_zonal_base import GceZonalBase
from util import gcp_utils
from util.gcp_utils import add_loaded_lib
from util.utils import log_time


class Instances(GceZonalBase):
    __lock = threading.Lock()

    @staticmethod
    @lru_cache(maxsize=1)
    def _create_cloudclient():

        logging.info("_cloudclient for %s", "Instances")
        # Local import to avoid burdening AppEngine memory.
        # Loading all Cloud Client libraries would be 100MB  means that
        # the default AppEngine Instance crashes on out-of-memory even before actually serving a request.
        from google.cloud import compute_v1

        add_loaded_lib("compute_v1")
        return compute_v1.InstancesClient()

    @classmethod
    def _cloudclient(cls, _=None):
        with cls.__lock:
            return cls._create_cloudclient()

    @staticmethod
    def method_names():
        return ["compute.instances.insert", "compute.instances.start"]

    def _gcp_instance_type(self, gcp_object: dict):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            machine_type = gcp_object["machineType"]
            ind = machine_type.rfind("/")
            machine_type = machine_type[ind + 1 :]
            return machine_type
        except KeyError:
            logging.exception("")
            return None

    def _list_all(self, project_id, zone) -> List[Dict]:
        # Local import to avoid burdening AppEngine memory.
        # Loading all Cloud Client libraries would be 100MB  means that
        # the default AppEngine Instance crashes on out-of-memory even before actually serving a request.
        from google.cloud import compute_v1

        add_loaded_lib("compute_v1")
        page_result = compute_v1.ListInstancesRequest(project=project_id, zone=zone)
        return self._list_resources_as_dicts(page_result)

    def _get_resource(self, project_id, zone, name) -> Optional[Dict]:
        try:
            # Local import to avoid burdening AppEngine memory. Loading all
            # Client libraries would be 100MB  means that the default AppEngine
            # Instance crashes on out-of-memory even before actually serving a request.
            from google.cloud import compute_v1

            add_loaded_lib("compute_v1")
            request = compute_v1.GetInstanceRequest(
                project=project_id, zone=zone, instance=name
            )

            return self._get_resource_as_dict(request)
        except errors.HttpError:
            logging.exception("")
            return None

    @log_time
    def label_resource(self, gcp_object, project_id):
        with self._write_lock:
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
            # Could use the Cloud Client as follows , but that apparently that does not support batching
            #  compute_v1.SetLabelsInstanceRequest(project=project_id, zone=zone, instance=name, labels=labels)
            self.counter += 1
            if self.counter >= self._BATCH_SIZE:
                self.do_batch()
