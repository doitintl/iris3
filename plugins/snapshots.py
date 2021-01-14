import logging

from googleapiclient import errors

from gce_base.gce_base import GceBase
from util import gcp_utils


class Snapshots(GceBase):
    def method_names(self):
        return ["compute.disks.createSnapshot"]

    def __list_snapshots(self, project_id):
        snapshots = []
        page_token = None
        more_results = True
        while more_results:
            try:
                result = (
                    self._google_client.snapshots()
                        .list(
                        project=project_id,
                        filter=self._filter_already_labeled,
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
            except errors.HttpError as e:
                logging.exception(e)

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

    def do_label(self, project_id):
        snapshots = self.__list_snapshots(project_id)
        for snapshot in snapshots:
            self.label_one(snapshot, project_id)
        if self.counter > 0:
            self.do_batch()
        return "OK", 200

    def get_gcp_object(self, data):
        try:
            if "response" not in data["protoPayload"]:
                return None
            request = data["protoPayload"]["request"]
            snap_name = request["name"]
            snapshot = self.__get_snapshot(
                data["resource"]["labels"]["project_id"], snap_name
            )
            return snapshot
        except Exception as e:
            logging.exception(e)
            return None

    def label_one(self, gcp_object, project_id):
        labels = self._build_labels(gcp_object, project_id)
        try:
            self._batch.add(
                self._google_client.snapshots().setLabels(
                    project=project_id,
                    resource=gcp_object["name"],
                    body=labels),
                request_id=gcp_utils.generate_uuid(),
            )
            self.counter += 1
            if self.counter == 1000:
                self.do_batch()
        except Exception as e:
            logging.exception(e)
            return "Error", 500
        return "OK", 200
