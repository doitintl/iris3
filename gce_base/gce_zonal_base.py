import logging
from abc import ABCMeta
from functools import lru_cache

from google.cloud import compute_v1

from gce_base.gce_base import GceBase
from util import gcp_utils
from util.utils import log_time, timing


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
            return gcp_utils.region_from_zone(zone)
        except KeyError as e:
            logging.exception(e)
            return None

    @lru_cache(maxsize=1)
    def _all_zones(self):
        """
         Get all available zones.
         NOTE! If different GCP Prpjects have different zones, this will break.
        But we assume that the zone list is the same for all as a performance boost

        """
        with timing("_all_zones"):
            # zones_client = compute_v1.ZonesClient()
            # project_id = gcp_utils.current_project_id()
            # request = compute_v1.ListZonesRequest(project=project_id)
            # zones = zones_client.list(request)
            # return  = [z.name for z in zones]
            # The above is slow
            return gcp_utils.predefined_zone_list()
