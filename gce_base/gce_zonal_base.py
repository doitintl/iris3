import logging
import threading
from abc import ABCMeta, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

from google.cloud import compute_v1

from gce_base.gce_base import GceBase
from util import gcp_utils
from util.utils import timing


class GceZonalBase(GceBase, metaclass=ABCMeta):
    zones_cloudclient = compute_v1.ZonesClient()

    def __init__(self):

        super().__init__()
        self._write_lock = threading.Lock()

    def _gcp_zone(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            return gcp_object["zone"].split("/")[-1]
        except KeyError as e:
            logging.exception("")
            return None

    def _gcp_region(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            zone = self._gcp_zone(gcp_object)
            return gcp_utils.region_from_zone(zone)
        except KeyError as e:
            logging.exception("")
            return None

    @classmethod
    @lru_cache(maxsize=1)
    def _all_zones(cls):
        """
        Get all available zones.
        The implementation gets the zones for one project only, but we assume that all GCP projects have the same zones.
        TODO The above is slow, potentially use the hardcoded list in gcp_utils. But if GOogle creates new zones, that will fail
        """
        with timing("_all_zones"):
            project_id = gcp_utils.current_project_id()
            request = compute_v1.ListZonesRequest(project=project_id)
            zones = cls.zones_cloudclient.list(request)
            return [z.name for z in zones]

    def label_all(self, project_id):
        with timing(f"label_all {type(self).__name__} in {project_id}"):
            self.label_by_zones(project_id, self._all_zones())
            if self.counter > 0:
                self.do_batch()

    # ef process_hello_world():
    #     def f(serial):
    #         time.sleep(1)
    #         return f"ended {serial}"

    #
    #     with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    #         futs = [executor.submit(f, serial) for serial in range(10)]
    #         rets = []
    #         for future in concurrent.futures.as_completed(futs):
    #             try:
    #                 rets.append(future.result())
    #             except Exception as exc:
    #                 print('%r generated an exception: %s' % (exc))
    #
    #     return f"Hello , {3}  threads done "

    def label_by_zones(self, project_id, zones):
        def label_one_zone(zone):
            with timing(
                f"zone {zone}, label_all {type(self).__name__} in {project_id}"
            ):
                for resource in self._list_all(project_id, zone):
                    try:
                        self.label_resource(resource, project_id)
                    except Exception as e:
                        logging.exception("in label_one_zone", exc_info=e)

        with ThreadPoolExecutor(max_workers=8) as executor:
            futs = [executor.submit(label_one_zone, zone) for zone in zones]
            for future in as_completed(futs):
                try:
                    _ = future.result()  # We Do not use ret; just a way of waiting
                except Exception as exc:
                    logging.exception("in getting result for future", exc_info=exc)

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
