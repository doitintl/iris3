import os
import os
import re
import uuid
from typing import Dict, Any, Generator

from util import localdev_config
from util.utils import timed_lru_cache, log_time, dict_to_camelcase


def detect_gae():
    gae_app = os.environ.get("GAE_APPLICATION", "")
    return "~" in gae_app


def current_project_id():
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
    """With the Google Cloud Libraries, we don't get these
    appscript sys- project, as we do with the Google API Client Libraries,
    but the filtering won't hurt."""
    return bool(re.match(r"sys-\d{26}", p))


# Not cached. Returns a generator, and so not reusable
def all_projects() -> Generator[str, Any, None]:
    # Local import to avoid burdening AppEngine memory. Loading all
    # Client libraries would be 100MB  means that the default AppEngine
    # Instance crashes on out-of-memory even before actually serving a request.

    from google.cloud import resourcemanager_v3

    projects_client = resourcemanager_v3.ProjectsClient()

    current_proj_id = current_project_id()
    current_project = projects_client.get_project(
        None, name=f"projects/{current_proj_id}"
    )
    parent_name = current_project.name
    org_name = get_org(parent_name)

    project_objects = projects_client.list_projects(parent=org_name)
    projects = (p.project_id for p in project_objects)
    return projects


def method_name(projects):
    return projects


@log_time
@timed_lru_cache(maxsize=250, seconds=600)
def get_org(proj_name):
    projects_client = __create_project_client()
    folders_client = __create_folder_client()
    assert proj_name.startswith(
        "projects/"
    ), f"Expect the form 'projects/123456789, was {proj_name}"
    parent_name = proj_name
    while True:
        if parent_name.startswith("projects/"):
            parent = projects_client.get_project(None, name=parent_name)
        elif parent_name.startswith("folders/"):
            parent = folders_client.get_folder(None, name=parent_name)
        elif parent_name.startswith("organizations/"):
            org_name = parent_name
            break
        else:
            raise Exception(
                f"expect projects/, folders/, or organizations/, was {parent_name}"
            )

        parent_name = parent.parent
    assert org_name.startswith(
        "organizations/"
    ), f"Expect the form 'organizations/123456789, was {org_name}"
    return org_name


def __create_folder_client():
    # Local import to avoid burdening AppEngine memory. Loading all
    # Client libraries would be 100MB  means that the default AppEngine
    # Instance crashes on out-of-memory even before actually serving a request.

    from google.cloud import resourcemanager_v3

    folders_client = resourcemanager_v3.FoldersClient()
    return folders_client


def __create_project_client():
    # Local import to avoid burdening AppEngine memory. Loading all
    # Client libraries would be 100MB  means that the default AppEngine
    # Instance crashes on out-of-memory even before actually serving a request.

    from google.cloud import resourcemanager_v3

    projects_client = resourcemanager_v3.ProjectsClient()
    return projects_client


@timed_lru_cache(maxsize=200, seconds=600)
def get_project(project_id: str) -> Dict[str, Any]:
    proj = __create_project_client().get_project(name=f"projects/{project_id}")
    proj_as_dict = {"labels": proj.labels}  # This is the only key actually used
    return proj_as_dict


def predefined_zone_list():
    return [
        "asia-east1-a",
        "asia-east1-b",
        "asia-east1-c",
        "asia-east2-a",
        "asia-east2-b",
        "asia-east2-c",
        "asia-northeast1-a",
        "asia-northeast1-b",
        "asia-northeast1-c",
        "asia-northeast2-a",
        "asia-northeast2-b",
        "asia-northeast2-c",
        "asia-northeast3-a",
        "asia-northeast3-b",
        "asia-northeast3-c",
        "asia-south1-a",
        "asia-south1-b",
        "asia-south1-c",
        "asia-south2-a",
        "asia-south2-b",
        "asia-south2-c",
        "asia-southeast1-a",
        "asia-southeast1-b",
        "asia-southeast1-c",
        "asia-southeast2-a",
        "asia-southeast2-b",
        "asia-southeast2-c",
        "australia-southeast1-a",
        "australia-southeast1-b",
        "australia-southeast1-c",
        "australia-southeast2-a",
        "australia-southeast2-b",
        "australia-southeast2-c",
        "europe-central2-a",
        "europe-central2-b",
        "europe-central2-c",
        "europe-north1-a",
        "europe-north1-b",
        "europe-north1-c",
        "europe-southwest1-a",
        "europe-southwest1-b",
        "europe-southwest1-c",
        # No "europe-west1-a", https://groups.google.com/g/gce-announce/c/uAXw_yYLEhw
        "europe-west1-b",
        "europe-west1-c",
        "europe-west1-d",
        "europe-west2-a",
        "europe-west2-b",
        "europe-west2-c",
        "europe-west3-a",
        "europe-west3-b",
        "europe-west3-c",
        "europe-west4-a",
        "europe-west4-b",
        "europe-west4-c",
        "europe-west6-a",
        "europe-west6-b",
        "europe-west6-c",
        "europe-west8-a",
        "europe-west8-b",
        "europe-west8-c",
        "europe-west9-a",
        "europe-west9-b",
        "europe-west9-c",
        "me-west1-a",
        "me-west1-b",
        "me-west1-c",
        "northamerica-northeast1-a",
        "northamerica-northeast1-b",
        "northamerica-northeast1-c",
        "northamerica-northeast2-a",
        "northamerica-northeast2-b",
        "northamerica-northeast2-c",
        "southamerica-east1-a",
        "southamerica-east1-b",
        "southamerica-east1-c",
        "southamerica-west1-a",
        "southamerica-west1-b",
        "southamerica-west1-c",
        "us-central1-a",
        "us-central1-b",
        "us-central1-c",
        "us-central1-f",
        "us-east5-a",
        "us-east5-b",
        "us-east5-c",
        "us-south1-a",
        "us-south1-b",
        "us-south1-c",
        "us-west1-a",
        "us-west1-b",
        "us-west1-c",
        "us-west2-a",
        "us-west2-b",
        "us-west2-c",
        "us-west3-a",
        "us-west3-b",
        "us-west3-c",
        "us-west4-a",
        "us-west4-b",
        "us-west4-c",
    ]


def cloudclient_pb_objects_to_list_of_dicts(objects):
    return (cloudclient_pb_obj_to_dict(i) for i in objects)


def cloudclient_pb_obj_to_dict(o) -> Dict[str, str]:
    keys = o.__dict__["_pb"].DESCRIPTOR.fields_by_name.keys()
    object_as_dict = {key: getattr(o, key) for key in keys}
    return dict_to_camelcase(object_as_dict)
