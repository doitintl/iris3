import json
import logging
import typing

from google.cloud.compute_v1 import Disk
from googleapiclient import errors

from gce_base.gce_zonal_base import GceZonalBase
from util import gcp_utils
from util.utils import log_time, to_camel_case
from util.utils import timing
from google.cloud import compute_v1 as compute_cloudclient


class Disks(GceZonalBase):
    disks_cloudclient = compute_cloudclient.DisksClient()

    """
    Label GCE disks. Boot disks created with instances only get labeled on the cron schedule.
    Independently created disks get labeled on creation.
    """

    def method_names(self):
        # As of 2021-1§0-12,   beta.compute.disks.insert
        return ["compute.disks.insert"]

    @classmethod
    def relabel_on_cron(cls) -> bool:
        """
        We need to relabel on cron  because:
        1. Though unattached disks are  labeled on creation,  attached disks are   not.
        2. A disk that changes attachment status does not get relabeled on-event
        """
        return True

    def __list_disks(self, project_id, zone) -> typing.List[typing.Dict]:
        # TODO could make this lazy
        request = compute_cloudclient.ListInstancesRequest(
            project=project_id, zone=zone
        )
        disks = list(self.disks_cloudclient.list(request))
        assert all(isinstance(i, Disk) for i in disks), [d.__class__ for d in disks]
        disks_as_dicts: typing.List[typing.Dict] = [
            self._cloudclient_pb_obj_to_dict(i) for i in disks
        ]
        return disks_as_dicts

    def __get_disk(self, project_id, zone, name):
        try:
            request = compute_cloudclient.GetDiskRequest(
                project=project_id, zone=zone, disk=name
            )

            disk = self.disks_cloudclient.get(request)

            return self._cloudclient_pb_obj_to_dict(disk)
        except errors.HttpError as e:
            logging.exception(e)
            return None

    def label_all(self, project_id):
        with timing(f"label_all(Disk) in {project_id}"):
            zones = self._all_zones()
            for zone in zones:
                disks = self.__list_disks(project_id, zone)
                for disk in disks:
                    try:
                        self.label_resource(disk, project_id)
                    except Exception as e:
                        logging.exception(e)

            if self.counter > 0:
                self.do_batch()

    def get_gcp_object(self, log_data):
        try:
            disk_name = log_data["protoPayload"]["resourceName"]
            ind = disk_name.rfind("/")
            disk_name = disk_name[ind + 1 :]
            labels = log_data["resource"]["labels"]
            disk = self.__get_disk(labels["project_id"], labels["zone"], disk_name)
            return disk
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
