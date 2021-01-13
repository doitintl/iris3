import logging

from googleapiclient import errors

from pluginbase import Plugin


class Cloudsql(Plugin):
    @classmethod
    def discovery_api(cls):
        return "sqladmin", "v1beta4"

    @classmethod
    def is_on_demand(cls) -> bool:
        """
        CloudSQL cannot be labeled on-demand since labels cannot be applied
        to CloudSQL during its long initialization phase.
        """
        return False

    def _get_name(self, gcp_object):
        """Method dynamically called in _gen_labels, so don't change name"""
        return self.name_no_separator(gcp_object)

    def _get_region(self, gcp_object):
        """Method dynamically called in _gen_labels, so don't change name"""
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

    def get_gcp_object(self, data):
        try:
            if "response" not in data["protoPayload"]:
                return None
            labels_ = data["resource"]["labels"]
            ind = labels_["database_id"].rfind(":")
            instance = labels_["database_id"][ind + 1 :]
            instance = self.__get_instance(labels_["project_id"], instance)
            return instance
        except Exception as e:
            logging.exception(e)
            return None

    def do_label(self, project_id):
        page_token = None
        more_results = True
        while more_results:
            try:
                response = (
                    self._google_client.instances()
                    .list(project=project_id, pageToken=page_token)
                    .execute()
                )
            except errors.HttpError as e:
                logging.exception(e)
                return
            if "items" not in response:
                return
            for database_instance in response["items"]:
                self.label_one(database_instance, project_id)
            if "nextPageToken" in response:
                page_token = response["nextPageToken"]
            else:
                more_results = False

    def label_one(self, gcp_object, project_id):
        # TODO use _build_labels for the following line
        labels = {"labels": self._gen_labels(gcp_object)}
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
            else:
                logging.exception(e)
        return "OK", 200
