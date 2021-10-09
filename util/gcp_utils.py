import os
import re
import uuid
from typing import List

from google.cloud import resource_manager

from util import localdev_config, config_utils
from util.localdev_config import localdev_pubsub_token

resource_manager_client = resource_manager.Client()


def detect_gae():
    gae_app = os.environ.get("GAE_APPLICATION", "")
    return "~" in gae_app


def project_id():
    """
    :return the project id on which we run AppEngine and PubSub
    """
    if detect_gae():
        return os.environ.get("GAE_APPLICATION", "").split("~")[1]
    else:
        return localdev_config.localdev_project_id()


def set_env():
    if not detect_gae():
        localdev_config.set_localdev_project_id_in_env()


def region_from_zone(zone):
    return zone[: len(zone) - 2].lower()


def generate_uuid() -> str:
    """
    :return a UUID as a string (and not an object or bytes);
     this is required by the http API.
    """
    return str(uuid.uuid4())


def pubsub_token():
    from_env = os.environ.get("PUBSUB_VERIFICATION_TOKEN")
    if from_env:
        return from_env
    else:
        return localdev_pubsub_token()


def all_projects() -> List[str]:
    all_proj = resource_manager_client.list_projects()
    return sorted([p.project_id for p in all_proj])


def is_appscript(p) -> bool:
    return bool(re.match(r"sys-\d{26}", p))
