import logging
from abc import ABCMeta

from googleapiclient import discovery, errors

import util.gcp_utils
from pluginbase import Plugin


class GceBase(Plugin, metaclass=ABCMeta):
    google_client = discovery.build('compute', 'v1')

    def __init__(self):
        super().__init__()
        # TODO The following line could be pulled up to the superclass. Maybe also the google_client= line above
        self.batch = self.google_client.new_batch_http_request(callback=self.batch_callback)

    def api_name(self):
        return 'compute.googleapis.com'

    def _get_name(self, gcp_object):
        """Method dynamically called in _gen_labels, so don't change name"""
        try:
            name = gcp_object['name']
            name = name.replace('.', '_').lower()[:62]
            return name
        except KeyError as e:
            logging.error(e)
            return None


    def build_labels(self, gcp_object):
        try:
            original_labels = gcp_object['labels']
        except KeyError:
            original_labels = {}
        gen_labels = self._gen_labels(gcp_object)
        all_labels = {**gen_labels, **original_labels}
        labels = {
            'labels': all_labels,
            'labelFingerprint': gcp_object.get('labelFingerprint', '')
        }
        return labels
