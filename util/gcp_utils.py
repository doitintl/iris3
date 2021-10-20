import os
import re
import uuid
from pprint import pprint
from typing import List, Dict, Any

from util import localdev_config

from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

resource_manager = discovery.build(
    "cloudresourcemanager",
    "v1",
    credentials=(GoogleCredentials.get_application_default()),
)


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
    :return a UUID as a string (and not an object or bytes);  this is required by the http API.
    """
    return str(uuid.uuid4())


def is_appscript_project(p) -> bool:
    return bool(re.match(r"sys-\d{26}", p))


def all_projects() -> List[str]:
    projs = []
    request = resource_manager.projects().list()
    while request is not None:
        response = request.execute()
        projs += [p["projectId"] for p in response.get("projects", [])]

        request = resource_manager.projects().list_next(
            previous_request=request, previous_response=response
        )
    return sorted(projs)


def get_project(project_id: str) -> Dict[str, Any]:
    projects = resource_manager.projects()
    request = projects.get(projectId=project_id)

    response = request.execute()
    return response
