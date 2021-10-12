import logging

from googleapiclient import errors

from plugin import Plugin
from util.utils import log_time, timing


class Cloudsql(Plugin):
    @classmethod
    def discovery_api(cls):
        return "sqladmin", "v1beta4"

    @classmethod
    def is_labeled_on_creation(cls) -> bool:
        """
        Labels cannot be applied to CloudSQL during its long initialization phase.
        Three log messages arrive (within 5 sec of each other) during initialization.
         At the first two, the CloudSQL Instance does not exist, and at the third, it is still PENDING.

        Maybe use Cloud Tasks instead of Pubsub to allow delay.
        1. Though Iris(Py2) used TaskQueue, it did NOT use delayed delivery  though it easily could  have.
        2. Apparently objects other than CloudSQL get correctly labeled 'on-creation' based on the log event.
        """
        return False

    def _gcp_name(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        return self._name_no_separator(gcp_object)

    def _gcp_region(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            region = gcp_object["region"]
            region = region.lower()
            return region
        except KeyError as e:
            logging.exception(e)
            return None

    def api_name(self):
        return "sqladmin.googleapis.com"

    def method_names(self):
        return ["cloudsql.instances.create"]

    def __get_instance(self, project_id, name):
        try:
            result = (
                self._google_client.instances()
                .get(project=project_id, instance=name)
                .execute()
            )
            return result
        except errors.HttpError as e:
            logging.exception(e)
            return None

    def get_gcp_object(self, log_data):
        try:
            if "response" not in log_data["protoPayload"]:
                return None
            labels_ = log_data["resource"]["labels"]
            ind = labels_["database_id"].rfind(":")
            instance = labels_["database_id"][ind + 1 :]
            instance = self.__get_instance(labels_["project_id"], instance)
            return instance
        except Exception as e:
            logging.exception(e)
            return None

    def label_all(self, project_id):
        with timing(f"label_all(CloudSQL) in {project_id}"):
            page_token = None
            while True:

                response = (
                    self._google_client.instances()
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
                    except Exception as e:
                        logging.exception(e)
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

            self._google_client.instances().patch(
                project=project_id,
                body=database_instance_body,
                instance=gcp_object["name"],
            ).execute()

        except errors.HttpError as e:
            if "PENDING_CREATE" == gcp_object.get("state"):
                logging.exception(
                    "CloudSQL cannot accept labels until it is fully initialized, which is why"
                    "we do not label it on-demand in the usual way",
                    exc_info=e,
                )

            raise e
