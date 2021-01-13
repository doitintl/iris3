import logging
import pkgutil
import typing
from abc import ABCMeta, abstractmethod

from googleapiclient import discovery

import util.config_utils
from util import config_utils, utils
from util.utils import cls_by_name

PLUGINS_MODULE = "plugins"


class Plugin(object, metaclass=ABCMeta):
    subclasses = []

    def __init__(self):
        self.counter = 0
        self._google_client = discovery.build(*self.discovery_api())
        self._batch = self._google_client.new_batch_http_request(
            callback=self.__batch_callback
        )

    @classmethod
    @abstractmethod
    def discovery_api(cls) -> typing.Tuple[str, str]:
        pass

    @classmethod
    def is_on_demand(cls) -> bool:
        """
        Only a few classes are  not-on-demand, and these classes should overwrite this method.
        """
        return True  # only a few are not-on-demand

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
        logging.info("gcp_object %s", gcp_object)

        # if utils.project_inheriting():
        #    labels = gcp.get_project_labels(gcp_object)
        # These label keys are the same across all Plugins
        label_keys = config_utils.get_labels()

        for label_key in label_keys:
            f = "_get_" + label_key
            if hasattr(self, f):
                func = getattr(self, f)
                label_value = func(gcp_object)
                labels[util.config_utils.iris_prefix() + "_" + label_key] = label_value
        return labels

    def __batch_callback(self, request_id, response, exception):
        if exception is not None:
            logging.error(
                "Error in Request Id: %s Response: %s Exception: %s",
                response,
                request_id,
                exception,
            )

    def do_batch(self):
        """In do_label, we loop over all objects. But for efficienccy, we do not process
        then all at once, but rather gather objects and process them in batches of
        1000 as we loop; then parse the remaining at the end of the loop"""
        try:
            self._batch.execute()
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
    def init(cls):
        def load_plugin_class(name):
            module_name = PLUGINS_MODULE + "." + name
            __import__(module_name)
            assert name == name.lower()
            plugin_cls = utils.cls_by_name(
                PLUGINS_MODULE + "." + name + "." + name.title()
            )
            return plugin_cls

        for _, module, _ in pkgutil.iter_modules([PLUGINS_MODULE]):
            plugin_class = load_plugin_class(module)
            Plugin.subclasses.append(plugin_class)

        assert Plugin.subclasses, "No plugins defined"

    @staticmethod
    def create_plugin(plugin_name: str) -> "Plugin":
        cls = cls_by_name(
            PLUGINS_MODULE + "." + plugin_name.lower() + "." + plugin_name
        )
        plugin = cls()
        return plugin

    # TODO use this in all subclasses; but check into whteher we should nest the labels as below.
    def _build_labels(self, gcp_object):
        try:
            original_labels = gcp_object["labels"]
        except KeyError:
            original_labels = {}
        gen_labels = self._gen_labels(gcp_object)
        all_labels = {**gen_labels, **original_labels}
        fingerprint = gcp_object.get("labelFingerprint", "")
        # TODO  labelFingerprint exists in GCE instances. In what other objects does it exist?
        logging.info(
            'For %s fingerprint was "%s"', self.__class__.__name__, fingerprint
        )
        labels = {"labels": all_labels, "labelFingerprint": fingerprint}
        return labels

    def name_after_slash(self, gcp_object):
        return self.__name(gcp_object, separator="/")

    def name_no_separator(self, gcp_object):
        return self.__name(gcp_object, separator="")

    def __name(self, gcp_object, separator=""):
        try:
            name = gcp_object["name"]
            if separator:
                index = name.rfind(separator)
                name = name[index + 1 :]
                name = name.replace(".", "_").lower()[:62]
                return name
        except KeyError as e:
            logging.exception(e)
            return None
