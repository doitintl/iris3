import logging
from abc import ABCMeta

from googleapiclient import discovery, errors

import util.gcp_utils
from pluginbase import Plugin
from util import gcp_utils


class GceBase(Plugin, metaclass=ABCMeta):
    google_client = discovery.build('compute', 'v1')

    def __init__(self):
        super().__init__()
        # TODO The following line, and google_client above, could be pulled up to the superclass.
        self.batch = self.google_client.new_batch_http_request(callback=self.batch_callback)

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
             #TODO can or should labelFingerprint technique be applied to all other object types?
            'labels': all_labels,
            'labelFingerprint': gcp_object.get('labelFingerprint', '')
        }
        return labels
