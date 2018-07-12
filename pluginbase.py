# a simple Python plugin loading system
# see http://stackoverflow.com/questions/14510286/plugin-architecture-plugin
# -manager-vs-inspecting-from-plugins-import

import logging

from utils import utils


class PluginMount(type):
    """
    A plugin mount point derived from:
        http://martyalchin.com/2008/jan/10/simple-plugin-framework/
    Acts as a metaclass which creates anything inheriting from Plugin
    """


    def __init__(cls, name, bases, attrs):
        """Called when a Plugin derived class is imported"""

        if not hasattr(cls, 'plugins'):
            # Called when the metaclass is first instantiated
            cls.plugins = []
        else:
            # Called when a plugin class is imported
            cls.register_plugin(cls)


    def register_plugin(cls, plugin):
        """Add the plugin to the plugin list and perform any registration
        logic"""

        # create a plugin instance and store it
        # optionally you could just store the plugin class and lazily
        # instantiate
        instance = plugin()

        # save the plugin reference
        cls.plugins.append(instance)

        # apply plugin logic - in this case connect the plugin to blinker
        # signals
        # this must be defined in the derived class
        instance.register_signals()


class Plugin(object):
    """A plugin which must provide a register_signals() method"""
    __metaclass__ = PluginMount


    def __init__(self):
        self.counter = 0
        self.tags = []
        self.on_demand = []
        self.batch = None


    def set_tags(self, tags):
        self.tags = tags


    def set_on_demand(self, on_demand):
        self.on_demand = on_demand


    def gen_labels(self, gcp_object):
        labels = {}
        for tag in self.tags:
            f = "_get_" + tag
            if f in dir(self):
                res = getattr(self, f)(gcp_object)
                if res is not None:
                    labels[utils.get_prfeix() + '_' + tag] = res
        return labels


    def batch_callback(self, request_id, response, exception):
        if exception is not None:
            logging.error(
                'Error in Request Id: {0} Response: {1} Exception: {2}'.format(
                    response, request_id,
                    exception))


    def is_on_demand(self):
        for od in self.on_demand:
            if self.__class__.__name__.lower() == od.lower():
                return True
        return False


    def do_batch(self):
        self.batch.execute()
        self.counter = 0


    def do_tag(self, project_id):
        raise NotImplementedError


    def get_gcp_object(self, data):
        raise NotImplementedError


    def tag_one(self, gcp_object, project_id):
        raise NotImplementedError


    def api_name(self):
        raise NotImplementedError


    def methodsNames(self):
        raise NotImplementedError


