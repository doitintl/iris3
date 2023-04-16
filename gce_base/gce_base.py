from abc import ABCMeta
from typing import Dict, Any

import proto

from plugin import Plugin
from util.gcp_utils import (
    cloudclient_pb_obj_to_dict,
    cloudclient_pb_objects_to_list_of_dicts,
)


class GceBase(Plugin, metaclass=ABCMeta):
    @staticmethod
    def _discovery_api():
        return "compute", "v1"

    def _gcp_name(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        return self._name_no_separator(gcp_object)

    def _get_resource_as_dict(self, request: proto.Message) -> Dict[str, Any]:
        inst = self._cloudclient().get(request)
        return cloudclient_pb_obj_to_dict(inst)

    def _list_resources_as_dicts(self, request: proto.Message):
        objects = self._cloudclient().list(request)  # Disk class
        return cloudclient_pb_objects_to_list_of_dicts(objects)
