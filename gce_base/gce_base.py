import typing
from abc import ABCMeta

from pluginbase import Plugin
from util import gcp_utils


class GceBase(Plugin, metaclass=ABCMeta):

    @classmethod
    def googleapiclient_discovery(cls) -> typing.Tuple[str, str]:
        return ('compute', 'v1')

    def api_name(self):
        return 'compute.googleapis.com'

    def _get_name(self, gcp_object):
        """Method dynamically called in _gen_labels, so don't change name"""
        return gcp_utils.get_name(gcp_object)

    def build_labels(self, gcp_object):
        try:
            original_labels = gcp_object['labels']
        except KeyError:
            original_labels = {}
        gen_labels = self._gen_labels(gcp_object)
        all_labels = {**gen_labels, **original_labels}
        labels = {
            # TODO can or should labelFingerprint technique be applied to all other object types?
            'labels': all_labels,
            'labelFingerprint': gcp_object.get('labelFingerprint', '')
        }
        return labels
