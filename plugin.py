import logging
import pkgutil
import re
import typing
from abc import ABCMeta, abstractmethod

from googleapiclient import discovery
from googleapiclient import errors

from util.config_utils import (
    is_copying_labels_from_project,
    possible_label_keys,
    iris_label_key_prefix,
)
from util.utils import cls_by_name, shorten

PLUGINS_MODULE = "plugins"


class Plugin(object, metaclass=ABCMeta):
    __project_access_client = discovery.build("cloudresourcemanager", "v1")
    __proj_regex = re.compile(r"[a-z]([-a-z0-9]*[a-z0-9])?")
    subclasses = []

    __label_chars = re.compile(r"[\w\d_-]")

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
    def is_labeled_on_creation(cls) -> bool:
        """
        Only a few classes are  labeled on creation, and these classes should override this method.
        """
        return True

    def __project_labels(self, project_id) -> typing.Dict:

        assert 6 <= len(project_id) <= 30
        assert self.__proj_regex.match(project_id), project_id

        request = self.__project_access_client.projects().get(projectId=project_id)
        try:
            response = request.execute()
            return response["labels"]
        except errors.HttpError as e:
            logging.exception(e)
            return {}

    def __iris_labels(self, gcp_object) -> typing.Dict:
        labels = {}
        # These label keys are the same across all Plugins
        label_keys = possible_label_keys()

        for label_key in label_keys:
            f = "_get_" + label_key
            if hasattr(self, f):
                func = getattr(self, f)
                label_value = func(gcp_object)
                # Only hyphens (-), underscores (_), lowercase characters,
                # and numbers are allowed. International characters are allowed.
                key = iris_label_key_prefix() + "_" + label_key
                label_value = self._make_legal_label_value(label_value)
                labels[key] = label_value
        return labels

    def __batch_callback(self, request_id, response, exception):
        # TODO Address this error, which is intermittent and found most often with disks.
        #  "Labels fingerprint either invalid or resource labels have changed".
        #  - Perhaps retry
        #  - Perhaps ignore and let the cron get it.
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
        except Exception as e:
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
    def label_one(self, gcp_object: typing.Dict, project_id: str):
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
            assert name == name.lower(), name
            plugin_cls = cls_by_name(PLUGINS_MODULE + "." + name + "." + name.title())
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

    def _build_labels(self, gcp_object, project_id):
        """
        :return Dict including original labels, project labels (if the system is configured to add those)
        and new labels.
        But if that would result in no change, return None
        """
        original_labels = gcp_object["labels"] if "labels" in gcp_object else {}
        project_labels = (
            self.__project_labels(project_id)
            if is_copying_labels_from_project()
            else {}
        )
        iris_labels = self.__iris_labels(gcp_object)
        all_labels = {**iris_labels, **project_labels, **original_labels}
        if all_labels == original_labels:
            logging.info(
                "Skip labeling %s because no change: %s",
                self.__class__.__name__,
                shorten(gcp_object),
            )
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

    @classmethod
    def _make_legal_label_value(cls, s):
        ret = "".join(c if cls.__label_chars.match(c) else "_" for c in s)
        ret = ret.lower()[:62]
        return ret
