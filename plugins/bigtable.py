import logging
import typing

from googleapiclient import errors

import util.gcp_utils
from plugin import Plugin
from util import gcp_utils


class Bigtable(Plugin):
    @classmethod
    def discovery_api(cls) -> typing.Tuple[str, str]:
        return "bigtableadmin", "v2"

    def api_name(self):
        return "bigtableadmin.googleapis.com"

    def method_names(self):
        return ["BigtableInstanceAdmin.CreateInstance"]

    def _get_name(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        return self._name_after_slash(gcp_object)

    def _get_zone(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            location = self.__get_location(
                gcp_object, gcp_object["project_id"])
            return location
        except KeyError as e:
            logging.exception(e)
            return None

    def _get_region(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            # project_id was added to the dict, in BigTable.label_one()
            zone = self.__get_location(gcp_object, gcp_object["project_id"])
            region = util.gcp_utils.region_from_zone(zone).lower()
            return region
        except KeyError as e:
            logging.exception(e)
            return None

    def _get_cluster(self, project_id, name):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            result = (
                self._google_client.projects()
                    .instances()
                    .clusters()
                    .list(parent="projects/" + project_id + "/instances/" + name)
                    .execute()
            )

            return result
        except errors.HttpError as e:
            logging.exception(e)
            return None

    def __get_location(self, gcp_object, project_id):
        instance = gcp_object["displayName"]
        result = self._get_cluster(project_id, instance)
        loc = result["clusters"][0]["location"]
        ind = loc.rfind("/")
        return loc[ind + 1:]

    def __get_instance(self, project_id, name):
        try:
            result = (
                self._google_client.projects()
                    .instances()
                    .get(name="projects/" + project_id + "/instances/" + name)
                    .execute()
            )
            return result
        except errors.HttpError as e:
            logging.exception(e)
            return None

    def get_gcp_object(self, data):
        try:
            instance = self.__get_instance(
                data["resource"]["labels"]["project_id"],
                data["protoPayload"]["request"]["instanceId"],
            )
            return instance
        except Exception as e:
            logging.exception(e)
            return None

    def do_label(self, project_id):
        page_token = None
        more_results = True
        while more_results:
            try:
                result = (
                    self._google_client.projects()
                        .instances()
                        .list(
                        parent="projects/" + project_id,
                        pageToken=page_token,
                        # Filter not supported
                    )
                        .execute()
                )
            except errors.HttpError as e:
                logging.exception(e)
                return
            if "instances" in result:
                for inst in result["instances"]:
                    self.label_one(inst, project_id)
            if "nextPageToken" in result:
                page_token = result["nextPageToken"]
            else:
                more_results = False
            if self.counter > 0:
                self.do_batch()

    def label_one(self, gcp_object, project_id):
        # This line, plus two lines down, are needed so that _get_region
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
                self._google_client.projects().instances().partialUpdateInstance(
                    name=gcp_object["name"],
                    body=gcp_object,
                    updateMask="labels"),
                request_id=gcp_utils.generate_uuid(),
            )
            self.counter += 1
            if self.counter == 1000:
                self.do_batch()
        except Exception as e:
            logging.exception(e)
        return "OK", 200
