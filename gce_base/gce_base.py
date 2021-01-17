import typing
from abc import ABCMeta

from plugin import Plugin


class GceBase(Plugin, metaclass=ABCMeta):
    _filter_already_labeled = "-labels.iris_name:*"  # Test filter

    @classmethod
    def discovery_api(cls) -> typing.Tuple[str, str]:
        return "compute", "v1"

    def api_name(self):
        return "compute.googleapis.com"

    def _get_name(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        return self._name_no_separator(gcp_object)
