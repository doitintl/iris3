import logging
from abc import ABCMeta
from functools import lru_cache
from typing import Dict, Any

import proto
from google.cloud import compute_v1

from gce_base.gce_base import GceBase
from util import gcp_utils
from util.gcp_utils import (
    cloudclient_pb_obj_to_dict,
    cloudclient_pb_objects_to_list_of_dicts,
)
from util.utils import timing


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

    @classmethod
    @lru_cache(maxsize=1)
    @timing
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

    def _get_resource_as_dict(self, request: proto.Message) -> Dict[str, Any]:
        inst = self._cloudclient().get(request)
        return cloudclient_pb_obj_to_dict(inst)

    def _list_resources_as_dicts(self, request: proto.Message):
        objects = self._cloudclient().list(request)  # Disk class
        return cloudclient_pb_objects_to_list_of_dicts(objects)
