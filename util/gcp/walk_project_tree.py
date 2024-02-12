import time
from itertools import chain

from google.cloud import resourcemanager_v3
from concurrent.futures import ThreadPoolExecutor

folders_client = resourcemanager_v3.FoldersClient()
proj_client = resourcemanager_v3.ProjectsClient()

def list_descendant_projects(container):
    """return iterator of project IDs, without "projects/" prefix """
    return filter(lambda n: not n.startswith("folders/"), _list_descendants(container))

def _list_descendants(container):
    """container: org or folder"""
    assert container.startswith("organizations/") or container.startswith(
        "folders/"
    ), container
    folders = list(
        __list_folders(container)
    )  # can't have generator because folders vbl used twice
    projects = __list_projects(container)
    with ThreadPoolExecutor() as executor:
        # Using  multithreading speeded a small sample from 15 sec to 6 sec
        descendants = chain(*executor.map(_list_descendants, folders))
    return filter(None,chain(folders, projects, descendants))


def __list_folders(container):
    req = resourcemanager_v3.ListFoldersRequest(parent=container)
    page_result = folders_client.list_folders(request=req)
    return ( resp.name  for resp in page_result)


def __list_projects(container):
    request_proj = resourcemanager_v3.ListProjectsRequest(parent=container)
    page_result = proj_client.list_projects(request=request_proj)
    return (resp.project_id for resp in page_result)


