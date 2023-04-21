import logging
from typing import Dict, Optional

from googleapiclient import errors

from plugin import Plugin
from util.utils import log_time, timing


class Cloudsql(Plugin):
    @staticmethod
    def _discovery_api():
        return "sqladmin", "v1beta4"

    @staticmethod
    def method_names():
        return ["cloudsql.instances.create"]

    @classmethod
    def _cloudclient(cls, _=None):
        logging.info("_cloudclient for %s", cls.__name__)
        raise NotImplementedError(
            "There is no Cloud Client library for " + cls.__name__
        )

    @staticmethod
    def is_labeled_on_creation() -> bool:
        """
        Labels cannot be applied to CloudSQL during its long initialization phase.

        Why:
            During initialization of CloudSQL Instance, 3 log messages arrive (within 5 sec of each other)
            At the first two, the CloudSQL Instance does not exist, and at the third, it is still PENDING.
        How:
            As an alternative, maybe use Cloud Tasks instead of Pubsub to allow delay.
        """
        return False

    def _gcp_name(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        return self._name_no_separator(gcp_object)

    def _gcp_region(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            return gcp_object["region"].lower()
        except KeyError:
            logging.exception("")
            return None

    def _get_resource(self, project_id, name):
        try:
            result = (
                self._google_api_client()
                .instances()
                .get(project=project_id, instance=name)
                .execute()
            )
            return result
        except errors.HttpError:
            logging.exception("")
            return None

    def get_gcp_object(self, log_data: Dict) -> Optional[Dict]:
        try:
            if "response" not in log_data["protoPayload"]:
                return None
            labels_ = log_data["resource"]["labels"]
            database_id = labels_["database_id"]
            instance = database_id[database_id.rfind(":") + 1 :]
            instance = self._get_resource(labels_["project_id"], instance)
            return instance
        except Exception:
            logging.exception("")
            return None

    def label_all(self, project_id):
        with timing(f"label_all({type(self).__name__}) in {project_id}"):
            page_token = None
            while True:
                response = (
                    self._google_api_client()
                    .instances()
                    .list(
                        project=project_id,
                        pageToken=page_token,
                        # Filter supported, but syntax not OK. We get this message: "Field not found. In
                        # expression labels.iris_name HAS *, At field labels ."
                    )
                    .execute()
                )

                if "items" not in response:
                    return
                for database_instance in response["items"]:
                    try:
                        self.label_resource(database_instance, project_id)
                    except Exception:
                        logging.exception("")
                if "nextPageToken" in response:
                    page_token = response["nextPageToken"]
                else:
                    return

    @log_time
    def label_resource(self, gcp_object, project_id):
        labels = self._build_labels(gcp_object, project_id)
        if labels is None:
            return
        try:
            database_instance_body = {"settings": {"userLabels": labels["labels"]}}

            self._google_api_client().instances().patch(
                project=project_id,
                body=database_instance_body,
                instance=gcp_object["name"],
            ).execute()

        except errors.HttpError as e:
            if "PENDING_CREATE" == gcp_object.get("state"):
                logging.exception(
                    "CloudSQL cannot accept labels until it is fully initialized, which is why"
                    "we do not label it on-demand in the usual way",
                )

            raise e
