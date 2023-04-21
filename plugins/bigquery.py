"""
Labeling BQ tables and datasets.
"""

import logging
from functools import lru_cache

from googleapiclient import errors
from ratelimit import limits, sleep_and_retry

from plugin import Plugin
from util import gcp_utils
from util.gcp_utils import add_loaded_lib
from util.utils import log_time, timing, dict_to_camelcase


class Bigquery(Plugin):
    @staticmethod
    def _discovery_api():
        return "bigquery", "v2"

    @classmethod
    @lru_cache(maxsize=500)  # cached per project
    def _cloudclient(cls, project_id=None):
        assert project_id, "'None' is only for the signature"
        logging.info("_cloudclient for %s", cls.__name__)
        # Local import to avoid burdening AppEngine memory.
        # Loading all Cloud Client libraries would be 100MB  means that
        # the default AppEngine Instance crashes on out-of-memory even before actually serving a request.
        from google.cloud import bigquery

        add_loaded_lib("bigquery")

        return bigquery.Client(project=project_id)

    @staticmethod
    def method_names():
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
        except KeyError:
            logging.exception("")
            return None

    def _gcp_location(self, gcp_object):
        """Method dynamically called in generating labels, so don't change name"""
        try:
            return gcp_object["location"].lower()
        except KeyError:
            logging.exception("")
            return None

    def __get_dataset(self, project_id, dataset_name):
        try:
            ds = self._cloudclient(project_id).get_dataset(
                f"{project_id}.{dataset_name}"
            )
            return self.__response_obj_to_dict(ds)
        except errors.HttpError:
            logging.exception("")
            return None

    @staticmethod
    def __response_obj_to_dict(ds_or_table):
        d1 = ds_or_table._properties
        d2 = {k: v for k, v in d1.items() if not k.startswith("_")}
        d3 = dict_to_camelcase(d2)
        return d3

    def __get_table(self, project_id, dataset, table):
        try:
            table = self._cloudclient(project_id).get_table(
                f"{project_id}.{dataset}.{table}"
            )
            return self.__response_obj_to_dict(table)
        except errors.HttpError:
            logging.exception("")
            return None

    def get_gcp_object(self, log_data):
        try:
            resource = log_data["protoPayload"]["serviceData"]["datasetInsertRequest"][
                "resource"
            ]
            dataset_name = resource["datasetName"]
            datasetid = dataset_name["datasetId"]
            projectid = dataset_name["projectId"]
            dataset = self.__get_dataset(projectid, datasetid)
            return dataset
        except Exception:
            # KeyError datasetInsertRequest occurs if this is actually a table-insert
            # No such dataset; hoping for table
            pass
        try:
            table = log_data["protoPayload"]["serviceData"]["tableInsertRequest"][
                "resource"
            ]["tableName"]
            tableid = table["tableId"]
            projectid_ = table["projectId"]
            datasetid = table["datasetId"]
            table = self.__get_table(projectid_, datasetid, tableid)
            return table
        except KeyError as ke:
            if "'serviceData'" in str(ke):
                logging.info("Cannot find serviceData for table")
            else:
                logging.exception("")
            return None
        except Exception:
            logging.exception("")
            return None

    def label_all(self, project_id):
        """
        Label both tables and data sets
        """
        with timing(f"label_all for BigQuery in {project_id}"):
            datasets = self._cloudclient(project_id).list_datasets()
            for dataset in datasets:
                self.__label_dataset_and_tables(project_id, dataset._properties)

            if self.counter > 0:
                self.do_batch()  # Used for Tables, not Datasets

    def __label_dataset_and_tables(self, project_id, dataset):
        self.__label_one_dataset(dataset, project_id)
        self.__label_tables_for_dataset(dataset, project_id)

    def __label_tables_for_dataset(self, dataset, project_id):
        ds_id = dataset["id"].replace(":", ".")
        for table in self._cloudclient(project_id).list_tables(dataset=ds_id):
            table_dict = table._properties
            table_dict["location"] = dataset["location"]
            self.__label_one_table(table_dict, project_id)

    @sleep_and_retry
    @limits(calls=35, period=60)
    def __label_one_dataset(self, gcp_object, project_id):
        labels = self._build_labels(gcp_object, project_id)
        if labels is None:
            return
        try:
            dataset_reference = gcp_object["datasetReference"]
            dataset_id = dataset_reference["datasetId"]

            assert (
                project_id == dataset_reference["projectId"]
            ), f"{project_id}!={dataset_reference['projectId']}"

            client = self._cloudclient(project_id)
            ds = client.get_dataset(f"{project_id}.{dataset_id}")
            ds.labels = labels["labels"]
            client.update_dataset(ds, ["labels"])
        except Exception:
            logging.exception("")

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
                self._google_api_client()
                .tables()
                .patch(
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
        except Exception:
            logging.exception("")

    @log_time
    def label_resource(self, gcp_object, project_id):
        try:
            if gcp_object["kind"] == "bigquery#dataset":
                self.__label_one_dataset(gcp_object, project_id)
            else:
                self.__label_one_table(gcp_object, project_id)
        except Exception:
            logging.exception("")
