import logging
import os
import re
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, Any, Generator
from zoneinfo import ZoneInfo

from google.appengine.api.runtime import memory_usage

from util import localdev_config, utils
from util.detect_gae import detect_gae
from util.utils import timed_lru_cache, log_time, dict_to_camelcase, sort_dict

__invocation_count = Counter()

global_counter = 0


def increment_invocation_count(path: str):
    global __invocation_count
    __invocation_count[path] += 1


def count_invocations_by_path():
    d = dict(__invocation_count)
    return sort_dict(d)


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
    """All projects to which the current user has access"""
    # Local import to avoid burdening AppEngine memory.
    # Loading all Cloud Client libraries would be 100MB  means that
    # the default AppEngine Instance crashes on out-of-memory even before actually serving a request.
    from google.cloud import resourcemanager_v3

    add_loaded_lib("resourcemanager_v3")
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
    # Local import to avoid burdening AppEngine memory.
    # Loading all Cloud Client libraries would be 100MB  means that
    # the default AppEngine Instance crashes on out-of-memory even before actually serving a request.

    from google.cloud import resourcemanager_v3

    add_loaded_lib("resourcemanager_v3")
    folders_client = resourcemanager_v3.FoldersClient()
    return folders_client


def __create_project_client():
    # Local import to avoid burdening AppEngine memory.
    # Loading all Cloud Client libraries would be 100MB  means that
    # the default AppEngine Instance crashes on out-of-memory even before actually serving a request
    from google.cloud import resourcemanager_v3

    add_loaded_lib("resourcemanager_v3")
    projects_client = resourcemanager_v3.ProjectsClient()
    return projects_client


@timed_lru_cache(maxsize=200, seconds=600)
def get_project(project_id: str) -> Dict[str, Any]:
    proj = __create_project_client().get_project(name=f"projects/{project_id}")
    proj_as_dict = {"labels": proj.labels}  # This is the only key actually used
    return proj_as_dict


def cloudclient_pb_objects_to_list_of_dicts(objects):
    return (cloudclient_pb_obj_to_dict(i) for i in objects)


def cloudclient_pb_obj_to_dict(o) -> Dict[str, str]:
    keys = o.__dict__["_pb"].DESCRIPTOR.fields_by_name.keys()
    object_as_dict = {key: getattr(o, key) for key in keys}
    return dict_to_camelcase(object_as_dict)


__inst_id = utils.random_str(6)

__loaded_libs = set()


def add_loaded_lib(s):
    __loaded_libs.add(s)


def log_gae_memory(tag):
    """Use this only in an AppEngine Request"""
    if detect_gae():
        try:
            libs = ",".join(__loaded_libs)
            curr_mem = __current_mem_usage_gae()
            logging.info(
                "GAEInst %s %s; %s; RAM %s; Libs:[%s];",
                __inst_id,
                count_invocations_by_path(),
                tag,
                f"{curr_mem}m",
                libs,
            )
        except Exception:
            logging.exception("")


def __current_mem_usage_gae() -> int:
    if detect_gae():
        try:
            mem_usage = round(memory_usage().current)
        except Exception:  # Can produce google.appengine.runtime.apiproxy_errors.ApplicationError
            mem_usage = -1
        return mem_usage
    else:
        return -1


@contextmanager
def gae_memory_logging(tag):
    log_gae_memory("start " + tag)
    yield
    log_gae_memory("end " + tag)


def enable_cloudprofiler():
    """# For Google Cloud Profiler,
    * set ENABLE_PROFILER to True above
    * edit requirements.txt as stated in requirements.txt
    * add a line to app.yaml as stated in requirements.txt
    """
    try:
        import googlecloudprofiler

        googlecloudprofiler.start()
    except (ValueError, NotImplementedError) as exc:
        localdev_error_msg = (
            ". Profiler is not supported in local development"
            if "Service name must be provided" in str(exc)
            else ""
        )

        logging.info(
            "Exception initializing the Cloud Profiler %s, %s", exc, localdev_error_msg
        )


def isonow_for_filename():
    now = datetime.now(tz=ZoneInfo("UTC"))
    s = now.strftime("%Y-%m-%dT%H.%M.%S.%f")
    s = s[:-3] + "Z"
    return s
