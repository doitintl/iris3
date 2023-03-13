import logging

from googleapiclient import errors

from gce_base.gce_base import GceBase
from util import gcp_utils
from util.utils import log_time, timing


class Snapshots(GceBase):
    def method_names(self):
        return ["compute.disks.createSnapshot"]

    def __list_snapshots(self, project_id):
        snapshots = []
        page_token = None
        more_results = True

        while more_results:
            result = (
                self._google_client.snapshots()
                .list(
                    project=project_id,
                    pageToken=page_token,
                )
                .execute()
            )
            if "items" in result:
                snapshots = snapshots + result["items"]
            if "nextPageToken" in result:
                page_token = result["nextPageToken"]
            else:
                more_results = False

        return snapshots

    def __get_snapshot(self, project_id, name):
        try:
            result = (
                self._google_client.snapshots()
                .get(project=project_id, snapshot=name)
                .execute()
            )
            return result
        except errors.HttpError as e:
            logging.exception(e)
            return None

    def label_all(self, project_id):
        with timing(f"label_all(Snapshot) in {project_id}"):
            snapshots = self.__list_snapshots(project_id)
            for snapshot in snapshots:
                try:
                    self.label_resource(snapshot, project_id)
                except Exception as e:
                    logging.exception(e)
            if self.counter > 0:
                self.do_batch()

    def get_gcp_object(self, log_data):
        try:
            if "response" not in log_data["protoPayload"]:
                return None
            request = log_data["protoPayload"]["request"]
            snap_name = request["name"]
            snapshot = self.__get_snapshot(
                log_data["resource"]["labels"]["project_id"], snap_name
            )
            return snapshot
        except Exception as e:
            logging.exception(e)
            return None

    @log_time
    def label_resource(self, gcp_object, project_id):
        labels = self._build_labels(gcp_object, project_id)

        self._batch.add(
            self._google_client.snapshots().setLabels(
                project=project_id, resource=gcp_object["name"], body=labels
            ),
            request_id=gcp_utils.generate_uuid(),
        )
        self.counter += 1
        if self.counter >= self._BATCH_SIZE:
            self.do_batch()
