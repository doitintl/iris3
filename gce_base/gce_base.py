import typing
from abc import ABCMeta

from pluginbase import Plugin


class GceBase(Plugin, metaclass=ABCMeta):
    @classmethod
    def discovery_api(cls) -> typing.Tuple[str, str]:
        return "compute", "v1"

    def api_name(self):
        return "compute.googleapis.com"

    def _get_name(self, gcp_object):
        """Method dynamically called in _gen_labels, so don't change name"""
        return self.name_no_separator(gcp_object)
