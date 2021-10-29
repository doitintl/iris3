import logging
from abc import ABCMeta

import util.gcp_utils
from gce_base.gce_base import GceBase


class GceZonalBase(GceBase, metaclass=ABCMeta):
    def _gcp_zone(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            return gcp_object["zone"].split("/")[-1]
        except KeyError as e:
            logging.exception(e)
            return None

    def _gcp_region(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            zone = self._gcp_zone(gcp_object)
            return util.gcp_utils.region_from_zone(zone)
        except KeyError as e:
            logging.exception(e)
            return None

    def _all_zones(self, project_id):
        """
        Get all available zones.
        """
        response = self._google_client.zones().list(project=project_id).execute()
        zones = [zone["description"] for zone in response["items"]]
        return zones

    def block_labeling(self, gcp_object, original_labels):
        # goog-gke-node appears in Nodes and Disks; and goog-gke-volume appears in Disks
        if "goog-gke-node" in original_labels or "goog-gke-volume" in original_labels:
            # We do not label GKE resources.
            logging.info(
                f"{self.__class__.__name__}, skip labeling GKE object {gcp_object.get('name')}"
            )
            return True
        else:
            return False
