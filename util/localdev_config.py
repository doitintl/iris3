import json
import os

import yaml


def __load_dev_config():
    with open("dev_config.json", "r") as config_file:
        config = json.load(config_file)
    return config


def local_gae_svc():
    with open("app.yaml") as file:
        documents = yaml.full_load(file)
        return documents.get("service", "default")


def localdev_project_id():
    config = __load_dev_config()
    return config["project"]


def localdev_projects():
    config = __load_dev_config()
    ret = config.get("dev_projects", [])
    assert isinstance(ret, (list,)), type(ret)
    return ret


def set_localdev_project_id_in_env():
    os.environ["GOOGLE_CLOUD_PROJECT"] = localdev_project_id()


def localdev_pubsub_token():
    with open("app.yaml") as file:
        documents = yaml.full_load(file)
        return documents["env_variables"]["PUBSUB_VERIFICATION_TOKEN"]
