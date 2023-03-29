import logging
import typing
from functools import lru_cache

from google.cloud import bigtable
from google.cloud.bigtable.instance import Instance
from googleapiclient import errors

from plugin import Plugin
from util import gcp_utils
from util.utils import log_time, timing


class Bigtable(Plugin):
    def __init__(self):
        super().__init__()
        self.bigtable_client = None

    @staticmethod
    def _discovery_api() -> typing.Tuple[str, str]:
        return "bigtableadmin", "v2"

    @staticmethod
    @lru_cache(maxsize=100)
    def _cloudclient(project_id: str) -> bigtable.Client():
        return bigtable.Client(project_id, admin=True)

    # @staticmethod
    # def api_name():
    #     return "bigtableadmin.googleapis.com"

    @staticmethod
    def method_names():
        return ["BigtableInstanceAdmin.CreateInstance"]

    def _gcp_display_name(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        return gcp_object.get("display_name", "")

    def _gcp_instance_id(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        return gcp_object.get("instance_id", "")

    # def _gcp_region(self, gcp_object): # must get from clusters!

    def __get_instance(self, project_id, inst_name):
        try:
            instance: Instance = self._cloudclient(project_id).instance(inst_name)
            if not instance.exists():
                logging.error("Bigtable instance %s does not exist", inst_name)
                return None
            else:
                return instance
        except errors.HttpError as e:
            logging.exception(e)
            return None

    def get_gcp_object(self, log_data):
        try:
            instance = self.__get_instance(
                log_data["resource"]["labels"]["project_id"],
                log_data["protoPayload"]["request"]["instanceId"],
            )
            return instance
        except Exception as e:
            logging.exception(e)
            return None

    def label_all(self, project_id):
        with timing(f"label_all(BigTable) in {project_id}"):
            instances_and_failed_locations = self._cloudclient(
                project_id
            ).list_instances()
            insts = instances_and_failed_locations[0]  #
            inst_to_dict = lambda i: {
                k: v
                for k, v in i.__dict__.items()
                if not k.startswith("_") and not k.endswith("_")
            }

            inst_dicts = (inst_to_dict(i) for i in insts)
            for inst in inst_dicts:
                self.label_resource(inst, project_id)
            if self.counter > 0:
                self.do_batch()

    @log_time
    def label_resource(self, gcp_object, project_id):
        labels = self._build_labels(gcp_object, project_id)
        if labels is None:
            return

        if "labels" not in gcp_object:
            gcp_object["labels"] = {}

        for key, val in labels["labels"].items():
            gcp_object["labels"][key] = val

        try:
            instance_path = (
                f"projects/{project_id}/instances/{gcp_object['instance_id']}"
            )
            self._batch.add(
                self._google_api_client()
                .projects()
                .instances()
                .partialUpdateInstance(
                    name=instance_path, body=gcp_object, updateMask="labels"
                ),
                request_id=gcp_utils.generate_uuid(),
            )
            self.counter += 1
            if self.counter >= self._BATCH_SIZE:
                self.do_batch()
        except Exception as e:
            logging.exception(e)
