import os
import typing
import uuid

from google.cloud import resource_manager


def detect_gae():
    gae_app = os.environ.get('GAE_APPLICATION', '')
    return  '~' in gae_app


def local_project_id():
    return 'joshua-playground2'


def local_gae_svc():
    return 'localservice'


def project_id():
    """
    Return the real or local project id.
   """
    if detect_gae():
       return os.environ.get('GAE_APPLICATION','').split('~')[1]
    else:
       return local_project_id()


def gae_url(path):
    if path[0]=='/':
        path=path[1:]
    return f'https://{gae_svc()}-dot-{project_id()}.{region()}.r.appspot.com/{path}'


def gae_svc():
    gae_svc = os.environ.get('GAE_SERVICE', local_gae_svc())
    return gae_svc


def get_all_projects()->typing.List[str]:
    projects=[p for p in resource_manager_client.list_projects()]
    return projects


def local_region():
    return 'localregion'


resource_manager_client = resource_manager.Client()


def region():
    if detect_gae():
        return os.environ.get('GAE_APPLICATION', '').split('~')[0]
    else:
        return local_region()


def region_from_zone(zone):
    return zone[:len(zone) - 2]



def generate_uuid(self):
        return str(uuid.uuid4())