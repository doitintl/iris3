"""
Labeling BQ tables and datasets.
"""
import logging
import typing

from googleapiclient import errors
from ratelimit import limits, sleep_and_retry

from plugin import Plugin
from util import gcp_utils
from util.utils import log_time, timing


class Bigquery(Plugin):
    @classmethod
    def discovery_api(cls) -> typing.Tuple[str, str]:
        return "bigquery", "v2"

    def api_name(self):
        return "bigquery-json.googleapis.com"

    def method_names(self):
        return ["datasetservice.insert", "tableservice.insert"]

    def _gcp_name(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            if gcp_object["kind"] == "bigquery#dataset":
                name = gcp_object["datasetReference"]["datasetId"]
            else:
                name = gcp_object["tableReference"]["tableId"]
            index = name.rfind(":")
            name = name[index + 1 :]
            return name
        except KeyError as e:
            logging.exception(e)
            return None

    def _gcp_location(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            location = gcp_object["location"]
            location = location.lower()
            return location
        except KeyError as e:
            logging.exception(e)
            return None

    def __get_dataset(self, project_id, name):
        try:
            result = (
                self._google_client.datasets()
                .get(projectId=project_id, datasetId=name)
                .execute()
            )
            return result
        except errors.HttpError as e:
            logging.exception(e)
            return None

    def __get_table(self, project_id, dataset, table):
        try:
            result = (
                self._google_client.tables()
                .get(projectId=project_id, datasetId=dataset, tableId=table)
                .execute()
            )
            return result
        except errors.HttpError as e:
            logging.exception(e)
            return None

    def get_gcp_object(self, log_data):
        try:
            proto_payload = log_data["protoPayload"]
            service_data = proto_payload["serviceData"]
            dataset_insert_request_ = service_data["datasetInsertRequest"]
            resource = dataset_insert_request_["resource"]
            dataset_name = resource["datasetName"]
            datasetid = dataset_name["datasetId"]
            projectid = dataset_name["projectId"]
            dataset = self.__get_dataset(projectid, datasetid)
            return dataset
        except Exception:
            # No such dataset; hoping for table
            pass
        try:
            proto_payload_ = log_data["protoPayload"]
            service_data_ = proto_payload_["serviceData"]
            table_insert_request_ = service_data_["tableInsertRequest"]
            resource_ = table_insert_request_["resource"]
            table = resource_["tableName"]
            tableid = table["tableId"]
            projectid_ = table["projectId"]
            datasetid = table["datasetId"]
            table = self.__get_table(projectid_, datasetid, tableid)
            return table
        except KeyError as ke:
            if "'serviceData'" in str(ke):
                logging.info("Cannot find serviceData for table")
            else:
                logging.exception(ke)
            return None
        except Exception as e:
            logging.exception(e)
            return None

    def label_all(self, project_id):
        """
        Label both tables and data sets
        """
        with timing(f"label_all for BigQuery in {project_id}"):
            page_token = None
            more_results = True
            while more_results:
                response = (
                    self._google_client.datasets()
                    .list(
                        projectId=project_id,
                        pageToken=page_token,
                        # Though filters are supported here, "NOT" filters are
                        # not
                    )
                    .execute()
                )

                if "datasets" in response:
                    for dataset in response["datasets"]:
                        self.__label_dataset_and_tables(project_id, dataset)
                if "nextPageToken" in response:
                    page_token = response["nextPageToken"]
                else:
                    more_results = False

    def __label_dataset_and_tables(self, project_id, dataset):
        self.__label_one_dataset(dataset, project_id)
        page_token = None
        more_results = True
        while more_results:
            response = (
                self._google_client.tables()
                .list(
                    projectId=project_id,
                    datasetId=dataset["datasetReference"]["datasetId"],
                    pageToken=page_token,
                    # filter not supported
                )
                .execute()
            )
            if "tables" in response:
                for t in response["tables"]:
                    t["location"] = dataset["location"]
                    self.__label_one_table(t, project_id)

            if "nextPageToken" in response:
                page_token = response["nextPageToken"]
                more_results = True
            else:
                more_results = False

    @sleep_and_retry
    @limits(calls=35, period=60)
    def __label_one_dataset(self, gcp_object, project_id):
        labels = self._build_labels(gcp_object, project_id)
        if labels is None:
            return
        try:
            dataset_reference = gcp_object["datasetReference"]
            self._google_client.datasets().patch(
                projectId=dataset_reference["projectId"],
                body=labels,
                datasetId=dataset_reference["datasetId"],
            ).execute()
        except Exception as e:
            logging.exception(e)

    @sleep_and_retry
    @limits(calls=35, period=60)
    def __label_one_table(self, gcp_object, project_id):
        """
        This often produces the following error. Hard to avoid, given that we are using batch operations. But
        that is why we sleep_and_retry, above.

        Error in Request Id: None Response: 72edf87e-d6fe-46b5-831a-e7b7bcd51cb0
        Exception: <HttpError 403 when requesting
        https://bigquery.googleapis.com/bigquery/v2/projects/fnx-poc-2020/datasets/monitoring/tables/10_most_%20expensive_jobs_today?alt=json
        returned "Exceeded rate limits: too many table update operations for this table.
        For more information, see https://cloud.google.com/bigquery/troubleshooting-errors".
        """
        labels = self._build_labels(gcp_object, project_id)
        if labels is None:
            return
        try:
            table_reference = gcp_object["tableReference"]
            self._batch.add(
                self._google_client.tables().patch(
                    projectId=table_reference["projectId"],
                    body=labels,
                    datasetId=table_reference["datasetId"],
                    tableId=table_reference["tableId"],
                ),
                request_id=gcp_utils.generate_uuid(),
            )
            self.counter += 1
            if self.counter >= self._BATCH_SIZE:
                self.do_batch()
        except Exception as e:
            logging.exception(e)
        if self.counter > 0:
            self.do_batch()

    @log_time
    def label_resource(self, gcp_object, project_id):
        try:
            if gcp_object["kind"] == "bigquery#dataset":
                self.__label_one_dataset(gcp_object, project_id)
            else:
                self.__label_one_table(gcp_object, project_id)
        except Exception as e:
            logging.exception(e)
