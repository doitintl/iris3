import functools
import logging
import os
import subprocess

import yaml


@functools.lru_cache
def __load_app_yaml():
    with open("app.yaml") as file:
        documents = yaml.full_load(file)
        return documents


@functools.lru_cache
def localdev_project_id():
    if project_id := os.environ.get("IRIS_PROJECT"):
        logging.info("Project %s (from env)", project_id)
        return project_id
    else:
        command = "gcloud config get-value project".split(" ")
        result = subprocess.run(command, stdout=subprocess.PIPE)
        project_id = result.stdout.decode("utf-8")
        project_id = project_id.strip("\n")
        logging.info("Project %s (from gcloud)", project_id)
        return project_id


def set_localdev_project_id_in_env():
    os.environ["GOOGLE_CLOUD_PROJECT"] = localdev_project_id()
