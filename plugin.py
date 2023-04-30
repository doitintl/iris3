import logging
import pkgutil
import re
import threading
from abc import ABCMeta, abstractmethod
from functools import lru_cache
from typing import Dict, Tuple, Type, Optional

from googleapiclient import discovery
from googleapiclient import errors

from util import gcp_utils, config_utils
from util.config_utils import (
    is_copying_labels_from_project,
    iris_prefix,
    specific_prefix,
)
from util.utils import (
    methods,
    cls_by_name,
    log_time,
    timed_lru_cache,
)

PLUGINS_MODULE = "plugins"


# TODO Since subclasses are already singletons, and we are already using
# a lot of classmethods and staticmethods, , could convert this to
# never use instance methods
class Plugin(metaclass=ABCMeta):
    # Underlying API  max is 1000; avoid off-by-one errors
    # We send a batch when _BATCH_SIZE or more tasks are in it, or at the end of a label_all
    _BATCH_SIZE = 990

    @staticmethod
    @abstractmethod
    def _discovery_api() -> Optional[Tuple[str, str]]:
        pass

    @staticmethod
    @abstractmethod
    def method_names():
        """The name of the methods inside the Google REST API that indicate the creation of such resources."""
        pass

    @staticmethod
    def relabel_on_cron() -> bool:
        """
        We must minimize labeling on cron because it is costly.
        Return  True if that is needed.
        When is_labeled_on_creation is False, we also label on cron
        """
        return False

    @staticmethod
    def is_labeled_on_creation() -> bool:
        """
        Only a few classes are  labeled on creation, and these classes should override this method.
        """
        return True

    @classmethod
    @lru_cache(maxsize=1)
    def _google_api_client(cls):

        discovery_api = cls._discovery_api()
        if discovery_api is not None:
            return discovery.build(*discovery_api)
        else:
            return None

    # All implementations of _cloudclient and _google_api_client should be thread-locked to avoid
    # creating multiple Cloud Clients or Google API Clients.
    # Still, there is no harm in occasional  multiple Clients.
    # We lock it only there there is a large chance of multiple simultaneous access.
    @classmethod  # Implementations should cache the result
    def _cloudclient(
        cls, project_id=None
    ):  # Some impl have project_id param, some don't
        raise NotImplementedError(
            "Implement this if you want to use the Cloud Client libraries"
        )

    def __init__(self):
        self.__init_batch_req()

    @timed_lru_cache(seconds=600, maxsize=512)
    def _project_labels(self, project_id) -> Dict:
        try:
            proj = gcp_utils.get_project(project_id)
            return proj.get("labels", {})
        except errors.HttpError:
            logging.exception("Failing to get labels for project {project_id}")
            return {}

    def __iris_labels(self, gcp_object) -> Dict[str, str]:
        func_name_pfx = "_gcp_"

        def legalize_value(s):
            """
            Only hyphens (-), underscores (_=None), lowercase characters,
            and numbers are allowed in label values. International characters are allowed.
            """
            label_chars = re.compile(r"[\w\d_-]")  # cached
            return "".join(c if label_chars.match(c) else "_" for c in s).lower()[:62]

        def value(func, gcp_obj):
            return legalize_value(func(gcp_obj))

        def key(func) -> str:
            general_pfx = iris_prefix()
            assert general_pfx is not None
            specific_pfx = specific_prefix(type(self).__name__)
            pfx = specific_pfx if specific_pfx is not None else general_pfx
            pfx_full = pfx + "_" if pfx else ""
            return pfx_full + func.__name__[len(func_name_pfx) :]

        # noinspection PyTypeChecker
        return {key(f): value(f, gcp_object) for f in methods(self, func_name_pfx)}

    # noinspection PyUnusedLocal
    def __batch_callback(self, request, response, exception):
        if exception is not None:
            logging.exception(
                "in __batch_callback(), %s",
                exc_info=exception,
            )

    def do_batch(self):
        """In main#do_label, we loop over all objects. But for efficienccy, we do not process
        then all at once, but rather gather objects and process them in batches of
        self._BATCH_SIZE as we loop; then parse the remaining at the end of the loop"""
        try:
            if self._batch is not None:
                self._batch.execute()
        except Exception:
            logging.exception("Exception executing _batch()")

        self.__init_batch_req()

    @abstractmethod
    def label_all(self, project_id):
        """Label all objects of a type in a given project"""
        pass

    @abstractmethod
    def get_gcp_object(self, log_data: Dict) -> Optional[Dict]:
        """Parse logging data to get a GCP object"""
        pass

    @abstractmethod
    def label_resource(self, gcp_object: Dict, project_id: str):
        """Label a single new object based on its description that comes from alog-line.
        Not clear why we cannot get the project_id out of the gcp_object since the PubSub/Logging
        messages seem to have this. Maybe one type of resource does not include project_id"""
        pass

    def _build_labels(self, gcp_object, project_id):
        """
        :return dict including original labels, project labels (if the system is configured to add those)
        and new labels. But if that would result in no change, return None
        """
        original_labels = gcp_object.get("labels", {})
        project_labels = (
            self._project_labels(project_id) if is_copying_labels_from_project() else {}
        )
        iris_labels = self.__iris_labels(gcp_object)
        all_labels = {**original_labels, **project_labels, **iris_labels}
        if all_labels == original_labels:
            # Skip labeling  because no change
            return None
        else:
            labels = {"labels": all_labels}
            fingerprint = gcp_object.get("labelFingerprint", "")
            if fingerprint:
                labels["labelFingerprint"] = fingerprint

            return labels

    def _name_after_slash(self, gcp_object):
        return self.__name(gcp_object, separator="/")

    def _name_no_separator(self, gcp_object):
        return self.__name(gcp_object, separator=None)

    def __name(self, gcp_object, separator: Optional[str] = None):
        try:
            name = gcp_object["name"]
            if separator:
                index = name.rfind(separator)
                name = name[index + 1 :]
            return name
        except KeyError:
            logging.exception("")
            return None

    def __init_batch_req(self):
        self.counter = 0
        google_api_client = self._google_api_client()
        if google_api_client is None:
            self._batch = None
        else:
            self._batch = google_api_client.new_batch_http_request(
                callback=self.__batch_callback
            )


class PluginHolder:
    # Map from class to instance
    plugins: Dict[Type[Plugin], Optional[Plugin]]
    plugins = {}
    __lock = threading.Lock()

    def __init__(self):
        raise NotImplementedError("Do not instantiate")

    @classmethod
    def plugin_cls_by_name(cls, name) -> Type[Plugin]:
        return cls_by_name(PLUGINS_MODULE + "." + name.lower() + "." + name.title())

    @classmethod
    @log_time
    def init(cls):
        def load_plugin_class(name) -> Type:
            module_name = PLUGINS_MODULE + "." + name
            __import__(module_name)
            assert name == name.lower()
            return cls.plugin_cls_by_name(name)

        loaded = []
        for _, module, _ in pkgutil.iter_modules([PLUGINS_MODULE]):
            if config_utils.is_plugin_enabled(module):
                plugin_class = load_plugin_class(module)
                cls.plugins[
                    plugin_class
                ] = None  # Initialize with NO instance to avoid importing
                loaded.append(plugin_class.__name__)


        assert cls.plugins, "No plugins defined"

    @classmethod
    def get_plugin_instance(cls, plugin_cls):
        with cls.__lock:
            assert plugin_cls in cls.plugins, plugin_cls + " " + cls.plugins
            plugin_instance = cls.plugins[plugin_cls]

            assert not plugin_instance or isinstance(
                plugin_instance, (Plugin, plugin_cls)
            )
            if plugin_instance is not None:
                return plugin_instance
            else:
                plugin_instance = plugin_cls()
                cls.plugins[plugin_cls] = plugin_instance
                return plugin_instance

    @classmethod
    def get_plugin_instance_by_name(cls, plugin_class_name: str):
        plugin_cls = cls.plugin_cls_by_name(plugin_class_name)
        return cls.get_plugin_instance(plugin_cls)
