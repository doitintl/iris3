import logging
import pkgutil
import re
import typing
from abc import ABCMeta, abstractmethod

from googleapiclient import discovery
from googleapiclient import errors

from util import gcp_utils, config_utils
from util.config_utils import is_copying_labels_from_project, iris_prefix
from util.utils import methods, cls_by_name, log_time, timed_lru_cache

PLUGINS_MODULE = "plugins"


class Plugin(object, metaclass=ABCMeta):
    __proj_regex = re.compile(r"[a-z]([-a-z0-9]*[a-z0-9])?")
    # Underlying API  max is 1000; avoid off-by-one errors
    # We send a batch when  _BATCH_SIZE or more tasks are in it.
    _BATCH_SIZE = 990

    # For a class to know its subclasses and their instances is generally bad.
    # We could create a separate PluginManager but let's not get too Java-ish.
    plugins: typing.Dict[str, "Plugin"]
    plugins = {}

    def __init__(self):
        self._google_client = discovery.build(*self.discovery_api())
        self.__init_batch_req()

    @classmethod
    @abstractmethod
    def discovery_api(cls) -> typing.Tuple[str, str]:
        pass

    @classmethod
    def relabel_on_cron(cls) -> bool:
        """
        We must minimize labeling on cron because it is costly.
        Return  True if that is needed.
        When is_labeled_on_creation is False, we also label on cron
        """
        return False

    @classmethod
    def is_labeled_on_creation(cls) -> bool:
        """
        Only a few classes are  labeled on creation, and these classes should override this method.
        """
        return True

    @timed_lru_cache(seconds=600, maxsize=512)
    def _project_labels(self, project_id) -> typing.Dict:

        assert self.__proj_regex.match(
            project_id
        ), f"Project ID is illegal: {project_id}"
        try:
            proj = gcp_utils.get_project(project_id)
            labels = proj.get("labels", {})
            return labels
        except errors.HttpError as e:
            logging.exception(f"Failing to get labels for project {project_id}: {e}")
            return {}

    def __iris_labels(self, gcp_object) -> typing.Dict[str, str]:
        func_name_pfx = "_gcp_"

        def legalize_value(s):
            """
            Only hyphens (-), underscores (_), lowercase characters,
            and numbers are allowed in label values. International characters are allowed.
            """
            label_chars = re.compile(r"[\w\d_-]")  # cached
            return "".join(c if label_chars.match(c) else "_" for c in s).lower()[:62]

        def value(func, gcp_obj):
            return legalize_value(func(gcp_obj))

        def key(func) -> str:
            iris_pfx = iris_prefix()
            iris_pfx_full = iris_pfx + "_" if iris_pfx else ""
            return iris_pfx_full + func.__name__[len(func_name_pfx) :]

        ret = {key(f): value(f, gcp_object) for f in methods(self, func_name_pfx)}

        return ret

    def __batch_callback(self, request_id, response, exception):
        if exception is not None:
            logging.exception(
                "in __batch_callback(), %s",
                exc_info=exception,
            )

    def do_batch(self):
        """In do_label, we loop over all objects. But for efficienccy, we do not process
        then all at once, but rather gather objects and process them in batches of
        self._BATCH_SIZE as we loop; then parse the remaining at the end of the loop"""
        try:
            self._batch.execute()
        except Exception as e:
            logging.exception(e)

        self.__init_batch_req()

    @abstractmethod
    def label_all(self, project_id):
        """Label all objects of a type in a given project"""
        pass

    @abstractmethod
    def get_gcp_object(self, log_data):
        """Parse logging data to get a GCP object"""
        pass

    @abstractmethod
    def label_resource(self, gcp_object: typing.Dict, project_id: str):
        """Tag a single new object based on its description that comes from alog-line"""
        pass

    @abstractmethod
    def api_name(self):
        pass

    @abstractmethod
    def method_names(self):
        pass

    @classmethod
    @log_time
    def init(cls):
        def load_plugin_class(name) -> typing.Type:
            module_name = PLUGINS_MODULE + "." + name
            __import__(module_name)
            assert name == name.lower(), name
            plugin_cls = cls_by_name(PLUGINS_MODULE + "." + name + "." + name.title())
            return plugin_cls

        for _, module, _ in pkgutil.iter_modules([PLUGINS_MODULE]):
            if config_utils.is_plugin_enabled(module):
                plugin_class = load_plugin_class(module)
                instance = plugin_class()
                Plugin.plugins[plugin_class.__name__] = instance

        assert Plugin.plugins, "No plugins defined"

    @staticmethod
    def get_plugin(plugin_name: str) -> "Plugin":
        return Plugin.plugins.get(plugin_name)

    def _build_labels(self, gcp_object, project_id):
        """
        :return dict including original labels, project labels (if the system is configured to add those)
        and new labels. But if that would result in no change, return None
        """
        original_labels = gcp_object["labels"] if "labels" in gcp_object else {}
        project_labels = (
            self._project_labels(project_id) if is_copying_labels_from_project() else {}
        )
        iris_labels = self.__iris_labels(gcp_object)
        all_labels = {**original_labels, **project_labels, **iris_labels}
        if self.block_labeling(gcp_object, original_labels):
            return None
        elif all_labels == original_labels:
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
        return self.__name(gcp_object, separator="")

    def __name(self, gcp_object, separator=""):
        try:
            name = gcp_object["name"]
            if separator:
                index = name.rfind(separator)
                name = name[index + 1 :]
            return name
        except KeyError as e:
            logging.exception(e)
            return None

    def __init_batch_req(self):
        self.counter = 0
        self._batch = self._google_client.new_batch_http_request(
            callback=self.__batch_callback
        )

    # Override and return True if this object must not be labeled (for example, GKE objects)
    def block_labeling(self, block_labeling, original_labels):
        return False
