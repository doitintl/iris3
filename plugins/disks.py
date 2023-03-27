import logging
import typing
from functools import lru_cache

from google.cloud import compute_v1
from googleapiclient import errors

from gce_base.gce_zonal_base import GceZonalBase
from util import gcp_utils
from util.utils import log_time
from util.utils import timing


class Disks(GceZonalBase):
    """
    Label GCE disks. Boot disks created with instances only get labeled on the cron schedule.
    Independently created disks get labeled on creation.
    """

    @classmethod
    @lru_cache(maxsize=1)
    def _cloudclient(cls):
        return compute_v1.DisksClient()

    def method_names(self):
        # As of 2021-10-12,   beta.compute.disks.insert
        return ["compute.disks.insert"]

    @classmethod
    def relabel_on_cron(cls) -> bool:
        """
        We need to relabel on cron  because:
        1. Though unattached disks are  labeled on creation,  attached disks are   not.
        2. A disk that changes attachment status does not get relabeled on-event
        """
        return True

    def _list_all(self, project_id, zone) -> typing.List[typing.Dict]:
        # TODO could make this lazy
        request = compute_v1.ListInstancesRequest(project=project_id, zone=zone)
        return self._list_resources_as_dicts(request)

    def _get_resource(self, project_id, zone, name):
        try:
            request = compute_v1.GetDiskRequest(
                project=project_id, zone=zone, disk=name
            )

            return self._get_resource_as_dict(request)
        except errors.HttpError as e:
            logging.exception(e)
            return None

    @log_time
    def label_resource(self, gcp_object, project_id):

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
