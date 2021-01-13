import logging
from abc import ABCMeta

import util.gcp_utils
from gce_base.gce_base import GceBase


class GceZonalBase(GceBase, metaclass=ABCMeta):
    def _get_zone(self, gcp_object):
        """Method dynamically called in _gen_labels, so don't change name"""
        try:
            zone = gcp_object["zone"]
            index = zone.rfind("/")
            zone = zone[index + 1 :]
            zone = zone.lower()
            return zone
        except KeyError as e:
            logging.exception(e)
            return None

    def _get_region(self, gcp_object):
        """Method dynamically called in _gen_labels, so don't change name"""
        try:
            zone = self._get_zone(gcp_object)
            region = util.gcp_utils.region_from_zone(zone).lower()
            return region
        except KeyError as e:
            logging.exception(e)
            return None

    def get_zones(self, project_id):
        """
        Get all available zones.
        """
        request = self._google_client.zones().list(project=project_id)
        response = request.execute()
        zones = [zone["description"] for zone in response["items"]]
        return zones
