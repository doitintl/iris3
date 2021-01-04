
import logging
from abc import ABCMeta, abstractmethod

import utils.conf_utils
from utils import conf_utils


class Plugin(object, metaclass=ABCMeta):
    plugins=[]
    on_demand=[]

    def __init__(self):
        self.counter = 0
        self.batch = None


    @classmethod
    def set_on_demand(cls, on_demand):
        """Set from config file. Only on-demand plugins will
        process each new object as it arrives, based on logs.
        As it happens, all plugins  as of 1.2021 are on-demand."""
        cls.on_demand = on_demand


    def _gen_labels(self, gcp_object):
        labels = {}
        configured_labels=conf_utils.get_labels()

        for lbl in configured_labels:#labels from class
            f = "_get_" + lbl
            if hasattr(self, f):
                func = getattr(self, f)
                label_value = func(gcp_object)
                labels[utils.conf_utils.get_iris_prefix() + '_' + lbl] = label_value
        return labels


    def batch_callback(self, request_id, response, exception):
        if exception is not None:
            logging.error(
                'Error in Request Id: {0} Response: {1} Exception: {2}'.format(
                    response, request_id,
                    exception))

    @classmethod
    def is_on_demand(cls):
        on_demand=[c.tolower() for c in cls.on_demand]
        return cls.__name__.lower() in on_demand


    def do_batch(self):
        """In do_label, we loop over all objects. But for efficienccy, we do not process
        then all at once, but rather gather objects and process them in batches of
        1000 as we loop; then parse the remaining at the end of the loop"""
        try:
          self.batch.execute()
        except TypeError as e:
          logging.exception(e)
        self.counter = 0

    @abstractmethod
    def do_label(self, project_id):
       """Label  all objects of a type"""
       pass

    @abstractmethod
    def get_gcp_object(self, log_data):
        """Parse logging data to get a GCP object"""
        pass

    @abstractmethod
    def label_one(self, gcp_object, project_id):
        """Tag a single new object based on its description that comes from alog-line"""
        pass

    #TODO Needed?
    @abstractmethod
    def api_name(self):
        pass

    @abstractmethod
    def method_names(self):
        pass


