import logging
from functools import lru_cache

from googleapiclient import errors

from gce_base.gce_base import GceBase
from util import gcp_utils
from util.gcp_utils import add_loaded_lib
from util.utils import log_time, timing


class Snapshots(GceBase):
    @classmethod
    @lru_cache(maxsize=1)
    def _cloudclient(cls, _=None):

        logging.info("_cloudclient for %s", cls.__name__)
        # Local import to avoid burdening AppEngine memory. Loading all
        # Client libraries would be 100MB  means that the default AppEngine
        # Instance crashes on out-of-memory even before actually serving a request.
        from google.cloud import compute_v1

        add_loaded_lib("compute_v1")
        return compute_v1.SnapshotsClient()

    @staticmethod
    def method_names():
        return ["compute.disks.createSnapshot", "compute.snapshots.insert"]

    def _list_all(self, project_id):
        # Local import to avoid burdening AppEngine memory. Loading all
        # Client libraries would be 100MB  means that the default AppEngine
        # Instance crashes on out-of-memory even before actually serving a request.
        from google.cloud import compute_v1

        add_loaded_lib("compute_v1")
        all_resources = compute_v1.ListSnapshotsRequest(project=project_id)
        return self._list_resources_as_dicts(all_resources)

    def _get_resource(self, project_id, name):
        try:
            # Local import to avoid burdening AppEngine memory.
            # Loading all Cloud Client libraries would be 100MB  means that
            # the default AppEngine Instance crashes on out-of-memory even before actually serving a request.
            from google.cloud import compute_v1

            add_loaded_lib("compute_v1")
            request = compute_v1.GetSnapshotRequest(project=project_id, snapshot=name)
            return self._get_resource_as_dict(request)
        except errors.HttpError:
            logging.exception("")
            return None

    def label_all(self, project_id):
        with timing(f"label_all in {project_id}"):
            for o in self._list_all(project_id):
                try:
                    self.label_resource(o, project_id)
                except Exception:
                    logging.exception("")
            if self.counter > 0:
                self.do_batch()

    def get_gcp_object(self, log_data):
        try:
            if "response" not in log_data["protoPayload"]:
                return None
            request = log_data["protoPayload"]["request"]
            name = request["name"]
            project_id = log_data["resource"]["labels"]["project_id"]

            return self._get_resource(project_id, name)
        except Exception:
            logging.exception("")
            return None

    @log_time
    def label_resource(self, gcp_object, project_id):
        labels = self._build_labels(gcp_object, project_id)

        self._batch.add(  # Using Google Client API because CloudClient has, I think, no batch functionality
            self._google_api_client()
            .snapshots()
            .setLabels(project=project_id, resource=gcp_object["name"], body=labels),
            request_id=gcp_utils.generate_uuid(),
        )
        self.counter += 1
        if self.counter >= self._BATCH_SIZE:
            self.do_batch()
