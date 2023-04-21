import logging
import threading
from abc import ABCMeta, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from typing import Dict, Optional

from gce_base.gce_base import GceBase
from util import gcp_utils
from util.gcp_utils import add_loaded_lib
from util.utils import timing


class GceZonalBase(GceBase, metaclass=ABCMeta):
    def __init__(self):

        super().__init__()
        self._write_lock = threading.Lock()

    @staticmethod
    @abstractmethod
    def _create_cloudclient():
        """This exists on GceZonalBase because of multithreaded access
        to zones, requiring some locking. Implementations of this method
        should cache the result."""
        pass

    def _gcp_zone(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            return gcp_object["zone"].split("/")[-1]
        except KeyError:
            logging.exception("")
            return None

    def _gcp_region(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            zone = self._gcp_zone(gcp_object)
            return gcp_utils.region_from_zone(zone)
        except KeyError:
            logging.exception("")
            return None

    @lru_cache(maxsize=1)
    def _all_zones(self):

        with timing("_all_zones"):
            project_id = gcp_utils.current_project_id()
            # Local import to avoid burdening AppEngine memory.
            # Loading all Cloud Client libraries would be 100MB  means that
            # the default AppEngine Instance crashes on out-of-memory even before actually serving a request.
            from google.cloud import compute_v1

            add_loaded_lib("compute_v1")

            request = compute_v1.ListZonesRequest(project=project_id)
            zones_client = compute_v1.ZonesClient()
            zones = zones_client.list(request)
            return [z.name for z in zones]

    def label_all(self, project_id):
        with timing(f"label_all {type(self).__name__} in {project_id}"):
            self.__label_by_zones(project_id, self._all_zones())
            if self.counter > 0:
                self.do_batch()

    def __label_by_zones(self, project_id, zones):
        def label_one_zone(zone):
            # with timing(
            #     f"zone {zone}, label_all {type(self).__name__} in {project_id}"
            # ):
            for resource in self._list_all(project_id, zone):
                try:
                    self.label_resource(resource, project_id)
                except Exception:
                    logging.exception("in label_one_zone")

        with ThreadPoolExecutor(max_workers=8) as executor:
            futs = [executor.submit(label_one_zone, zone) for zone in zones]
            for future in as_completed(futs):
                try:
                    _ = future.result()  # We Do not use ret; just a way of waiting
                except Exception:
                    logging.exception("Error getting result for future")

    def get_gcp_object(self, log_data: Dict) -> Optional[Dict]:
        try:
            name = log_data["protoPayload"]["resourceName"]
            idx = name.rfind("/")
            name = name[idx + 1 :]
            project_id = log_data["resource"]["labels"]["project_id"]
            zone = log_data["resource"]["labels"]["zone"]
            resource = self._get_resource(project_id, zone, name)
            return resource
        except Exception:
            logging.exception("get_gcp_object")
            return None

    @abstractmethod
    def _get_resource(self, project_id, zone, name):
        pass

    @abstractmethod
    def _list_all(self, project_id, zone):
        pass
