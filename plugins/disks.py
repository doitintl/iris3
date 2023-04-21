import logging
import threading
import typing
from functools import lru_cache

from googleapiclient import errors

from gce_base.gce_zonal_base import GceZonalBase
from util import gcp_utils
from util.gcp_utils import add_loaded_lib
from util.utils import log_time


class Disks(GceZonalBase):
    """
    Label GCE disks. Boot disks created with instances only get labeled on the cron schedule.
    Independently created disks get labeled on creation.
    """

    __lock = threading.Lock()

    @staticmethod
    @lru_cache(maxsize=1)
    def _create_cloudclient():
        logging.info("_cloudclient for %s", "Disks")
        # Local import to avoid burdening AppEngine memory.
        # Loading all Cloud Client libraries would be 100MB  means that
        # the default AppEngine Instance crashes on out-of-memory even before actually serving a request.
        from google.cloud import compute_v1

        add_loaded_lib("compute_v1")
        return compute_v1.DisksClient()

    @classmethod
    def _cloudclient(cls, _=None):
        with cls.__lock:
            return cls._create_cloudclient()

    @staticmethod
    def method_names():
        # As of 2021-10-12,   beta.compute.disks.insert
        return ["compute.disks.insert"]

    @staticmethod
    def relabel_on_cron() -> bool:
        """
        We need to relabel on cron  because:
        1. Though unattached disks are  labeled on creation,  attached disks are   not.
        2. A disk that changes attachment status does not get relabeled on-event
        """
        return True

    def _list_all(self, project_id, zone) -> typing.List[typing.Dict]:
        # Local import to avoid burdening AppEngine memory.
        # Loading all Cloud Client libraries would be 100MB  means that
        # the default AppEngine Instance crashes on out-of-memory even before actually serving a request.
        from google.cloud import compute_v1

        add_loaded_lib("compute_v1")
        request = compute_v1.ListDisksRequest(project=project_id, zone=zone)
        return self._list_resources_as_dicts(request)

    def _get_resource(self, project_id, zone, name):
        try:
            # Local import to avoid burdening AppEngine memory.
            # Loading all Cloud Client libraries would be 100MB  means that
            # the default AppEngine Instance crashes on out-of-memory even before actually serving a request.
            from google.cloud import compute_v1

            add_loaded_lib("compute_v1")
            request = compute_v1.GetDiskRequest(
                project=project_id, zone=zone, disk=name
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
                .disks()
                .setLabels(
                    project=project_id,
                    zone=zone,
                    resource=gcp_object["name"],
                    body=labels,
                ),
                request_id=gcp_utils.generate_uuid(),
            )
            self.counter += 1
            if self.counter >= self._BATCH_SIZE:
                self.do_batch()

    def _gcp_pd_attached(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        users = gcp_object.get("users")
        return "true" if users else "false"
