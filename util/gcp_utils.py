import os

from google.cloud import resourcemanager_v3

from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

resource_manager = discovery.build(
    "cloudresourcemanager",
    "v1",
    credentials=(GoogleCredentials.get_application_default()),
)
projects_client = resourcemanager_v3.ProjectsClient()
folders_client = resourcemanager_v3.FoldersClient()


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
        return "joshua-playground"


def implementation1():
    projs = []
    request = resource_manager.projects().list()
    while request is not None:
        response = request.execute()
        projs += [p["projectId"] for p in response.get("projects", [])]

        request = resource_manager.projects().list_next(
            previous_request=request, previous_response=response
        )
    return sorted(projs)





def list_projects():
    current_project = projects_client.get_project(None, name="projects/joshua-playground")
    parent_name = current_project.name
    org_name = get_org(  parent_name)

    projects = projects_client.list_projects(parent=org_name)
    ret = [p.project_id for p in projects]
    return ret


def get_org(proj_name):
    assert proj_name.startswith("projects"), f"Expect the form 'projects/123456789, was {proj_name}"
    parent_name=proj_name
    while True:
        if parent_name.startswith("projects/"):
            parent = projects_client.get_project(None, name=parent_name)
        elif parent_name.startswith("folders/"):
            parent = folders_client.get_folder(None, name=parent_name)
        elif parent_name.startswith("organizations/"):
            org_name = parent_name
            break
        else:
            raise Exception(parent_name)

        parent_name = parent.parent
    return org_name

proj_1=implementation1()
proj_1=[p for p in proj_1 if not p.startswith('sys-')]
proj2 = list_projects()

d1 = set(proj_1) - set(proj2)
print("difference1", len(d1), d1)
print()
print()
print()


print("difference2", set(proj2) - set(proj_1))
#
