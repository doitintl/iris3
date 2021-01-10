import logging
import pkgutil
import typing
from abc import ABCMeta, abstractmethod

import util.config_utils
from util import config_utils, utils
from util.utils import cls_by_name

PLUGINS_MODULE = 'plugins'


class Plugin(object, metaclass=ABCMeta):
    subclasses = []
    on_demand: bool = False

    def __init__(self):
        # These are set in subclass; We have it here to keep IDEs happy.
        self.counter = 0
        self.batch = None

    @classmethod
    def set_on_demand(cls, on_demand: bool):
        """Set from config file. Only on-demand plugin classes will
        process each new object as it arrives, based on logs, using label_one().
        Otherwise, the plugin will only process objects based on cron (schedule() and do_label())
        """
        cls.on_demand = on_demand

    # TODO  Project labels: Copy the labels of a project to the objects in the project.
    # def get_project_labels(self, gcp_object):
    #    from googleapiclient import discovery
    #    project_id=gcp_object['id'].split(':')[0]
    #    service = discovery.build(
    #        'cloudresourcemanager', 'v1')
    #
    #    request = service.projects().get(projectId=project_id)
    #    response = request.execute()
    #    if 'labels' in response:
    #        return response['labels']
    #    else:
    #        return {}

    def _gen_labels(self, gcp_object):
        labels = {}
        # TODO Remove excess logs
        logging.info('gcp_object %s', gcp_object)
        # if utils.project_inheriting():
        #
        #    labels = gcp.get_project_labels(gcp_object)
        # These label keys are the same across all Plugins
        label_keys = config_utils.get_labels()

        for label_key in label_keys:
            f = '_get_' + label_key
            if hasattr(self, f):
                func = getattr(self, f)
                label_value = func(gcp_object)
                labels[util.config_utils.iris_prefix() + '_' + label_key] = label_value
        return labels

    def batch_callback(self, request_id, response, exception):
        if exception is not None:
            logging.error('Error in Request Id: %s Response: %s Exception: %s', response, request_id, exception)

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
        """Label all objects of a type in a given project"""
        pass

    @abstractmethod
    def get_gcp_object(self, log_data):
        """Parse logging data to get a GCP object"""
        pass

    @abstractmethod
    def label_one(self, gcp_object, project_id):
        """Tag a single new object based on its description that comes from alog-line"""
        pass

    @abstractmethod
    def api_name(self):
        pass

    @abstractmethod
    def method_names(self):
        pass

    @classmethod
    def init_plugins(cls):
        on_demand_plugins: typing.List[str] = config_utils.on_demand_plugins()
        for _, module, _ in pkgutil.iter_modules([PLUGINS_MODULE]):
            plugin_class = Plugin.__load_plugin_class(module)
            Plugin.subclasses.append(plugin_class)
            plugin_class.set_on_demand(plugin_class.__name__ in on_demand_plugins)

        assert Plugin.subclasses, 'No plugins defined'

    @staticmethod
    def __load_plugin_class(name):
        module_name = PLUGINS_MODULE + '.' + name
        __import__(module_name)
        assert name == name.lower()
        cls = utils.cls_by_name(PLUGINS_MODULE + '.' + name + '.' + name.title())
        return cls

    @staticmethod
    def create_plugin(plugin_name: str) -> 'Plugin':
        cls = cls_by_name(PLUGINS_MODULE + '.' + plugin_name.lower() + '.' + plugin_name)
        plugin = cls()
        return plugin
