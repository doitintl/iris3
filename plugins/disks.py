import logging

from googleapiclient import errors

from gce_base.gce_zonal_base import GceZonalBase
from util import gcp_utils


class Disks(GceZonalBase):
    """
    Label GCE disks. Boot disks created with instances only get labeled on the cron schedule.
    Independently created disks get labeled on creation.
    """

    def method_names(self):
        return ["v1.compute.disks.insert"]

    def __list_disks(self, project_id, zone):
        disks = []
        page_token = None
        more_results = True
        while more_results:
            try:
                result = (
                    self._google_client.disks()
                    .list(
                        project=project_id,
                        zone=zone,
                        filter=self._filter_already_labeled,
                        pageToken=page_token,
                    )
                    .execute()
                )
                if "items" in result:
                    disks = disks + result["items"]
                if "nextPageToken" in result:
                    page_token = result["nextPageToken"]
                else:
                    more_results = False
            except errors.HttpError as e:
                logging.exception(e)
                more_results = False

        return disks

    def __get_disk(self, project_id, zone, name):
        try:
            result = (
                self._google_client.disks()
                .get(project=project_id, zone=zone, disk=name)
                .execute()
            )
            return result
        except errors.HttpError as e:
            logging.exception(e)
            return None

    def do_label(self, project_id):
        for zone in self._all_zones(project_id):
            disks = self.__list_disks(project_id, zone)
            for disk in disks:
                self.label_one(disk, project_id)
        if self.counter > 0:
            self.do_batch()
        return "OK", 200

    def get_gcp_object(self, data):
        try:
            disk_name = data["protoPayload"]["resourceName"]
            ind = disk_name.rfind("/")
            disk_name = disk_name[ind + 1 :]
            labels = data["resource"]["labels"]
            disk = self.__get_disk(labels["project_id"], labels["zone"], disk_name)
            return disk
        except Exception as e:
            logging.exception(e)
            return None

    def label_one(self, gcp_object, project_id):
        labels = self._build_labels(gcp_object, project_id)
        if labels is None:
            return
        try:
            zone = self._gcp_zone(gcp_object)

            self._batch.add(
                self._google_client.disks().setLabels(
                    project=project_id,
                    zone=zone,
                    resource=gcp_object["name"],
                    body=labels,
                ),
                request_id=gcp_utils.generate_uuid(),
            )
            self.counter += 1
            if self.counter == self._BATCH_SIZE:
                self.do_batch()

        except errors.HttpError as e:
            logging.exception(e)
            return "Error", 500
        return "OK", 200
