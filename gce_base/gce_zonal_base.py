import logging
from abc import ABCMeta
from functools import lru_cache

from google.cloud import compute_v1

from gce_base.gce_base import GceBase
from util import gcp_utils
from util.utils import log_time, timing


class GceZonalBase(GceBase, metaclass=ABCMeta):
    zones_cloudclient = compute_v1.ZonesClient()

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
    @timing
    @classmethod
    def _all_zones(cls):
        """
        Get all available zones.
        NOTE! Because of caching, if different GCP Projects have different zones, this will break.
        """

        project_id = gcp_utils.current_project_id()
        request = compute_v1.ListZonesRequest(project=project_id)
        zones = cls.zones_cloudclient.list(request)
        return [z.name for z in zones]
        # The above is slow, potentially use the hardcoded list in gcp_utils
