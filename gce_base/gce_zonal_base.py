import logging
from abc import ABCMeta, abstractmethod
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

    def label_all(self, project_id):
        with timing(f"label_all  in {project_id}"):
            zones = self._all_zones()
            for zone in zones:
                for resource in self._list_all(project_id, zone):
                    try:
                        self.label_resource(resource, project_id)
                    except Exception as e:
                        logging.exception(e)

            if self.counter > 0:
                self.do_batch()

    def get_gcp_object(self, log_data):
        try:
            name = log_data["protoPayload"]["resourceName"]
            ind = name.rfind("/")
            name = name[ind + 1 :]
            project_id = log_data["resource"]["labels"]["project_id"]
            zone = log_data["resource"]["labels"]["zone"]
            resource = self._get_resource(project_id, zone, name)
            return resource
        except Exception as e:
            logging.exception("get_gcp_object", exc_info=e)
            return None

    @abstractmethod
    def _get_resource(self, project_id, zone, name):
        pass

    @abstractmethod
    def _list_all(self, project_id, zone):
        pass
