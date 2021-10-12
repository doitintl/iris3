import logging
import typing

from googleapiclient import errors

import util.gcp_utils
from plugin import Plugin
from util import gcp_utils
from util.utils import log_time, timing

PROJECTS = "projects/"


class Bigtable(Plugin):
    @classmethod
    def discovery_api(cls) -> typing.Tuple[str, str]:
        return "bigtableadmin", "v2"

    def api_name(self):
        return "bigtableadmin.googleapis.com"

    def method_names(self):
        return ["BigtableInstanceAdmin.CreateInstance"]

    def _gcp_name(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        return self._name_after_slash(gcp_object)

    def _gcp_zone(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            zone = self.__get_location(gcp_object, gcp_object["project_id"])
            return zone
        except KeyError as e:
            logging.exception(e)
            return None

    def _gcp_region(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            # project_id was added to the dict, in BigTable.label_one()
            zone = self.__get_location(gcp_object, gcp_object["project_id"])
            region = util.gcp_utils.region_from_zone(zone)
            return region
        except KeyError as e:
            logging.exception(e)
            return None

    def __get_cluster(self, project_id, instance_name):
        try:

            result = (
                self._google_client.projects()
                .instances()
                .clusters()
                .list(parent=PROJECTS + project_id + "/instances/" + instance_name)
                .execute()
            )

            return result
        except errors.HttpError as e:
            logging.exception(e)
            return None

    def __get_location(self, gcp_object, project_id):
        instance = gcp_object["displayName"]
        result = self.__get_cluster(project_id, instance)
        loc = result["clusters"][0]["location"]
        return loc.split("/")[-1]

    def __get_instance(self, project_id, name):
        try:
            result = (
                self._google_client.projects()
                .instances()
                .get(name=PROJECTS + project_id + "/instances/" + name)
                .execute()
            )
            return result
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
            page_token = None
            more_results = True
            while more_results:
                result = (
                    self._google_client.projects()
                    .instances()
                    .list(
                        parent=PROJECTS + project_id,
                        pageToken=page_token,
                        # Filter not supported
                    )
                    .execute()
                )

                if "instances" in result:
                    for inst in result["instances"]:
                        try:
                            self.label_resource(inst, project_id)
                        except Exception as e:
                            logging.exception(e)
                if "nextPageToken" in result:
                    page_token = result["nextPageToken"]
                else:
                    more_results = False
                if self.counter > 0:
                    self.do_batch()

    @log_time
    def label_resource(self, gcp_object, project_id):
        # This line, plus two lines down, are needed so that _gcp_region
        # can get the project_id
        gcp_object["project_id"] = project_id
        labels = self._build_labels(gcp_object, project_id)
        if labels is None:
            return
        del gcp_object["project_id"]
        if "labels" not in gcp_object:
            gcp_object["labels"] = {}

        for key, val in labels["labels"].items():
            gcp_object["labels"][key] = val

        try:

            self._batch.add(
                self._google_client.projects()
                .instances()
                .partialUpdateInstance(
                    name=gcp_object["name"], body=gcp_object, updateMask="labels"
                ),
                request_id=gcp_utils.generate_uuid(),
            )
            self.counter += 1
            if self.counter >= self._BATCH_SIZE:
                self.do_batch()
        except Exception as e:
            logging.exception(e)
