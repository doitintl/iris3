import logging
from abc import ABCMeta

import util.gcp_utils
from gce_base.gce_base import GceBase


class GceZonalBase(GceBase, metaclass=ABCMeta):
    def _get_zone(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            zone = gcp_object["zone"].split("/")[-1]
            return zone
        except KeyError as e:
            logging.exception(e)
            return None

    def _get_region(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            zone = self._get_zone(gcp_object)
            region = util.gcp_utils.region_from_zone(zone).lower()
            return region
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
