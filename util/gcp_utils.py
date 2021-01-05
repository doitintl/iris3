import logging
import os
import typing
import uuid

from google.cloud import resource_manager

resource_manager_client = resource_manager.Client()


def detect_gae():
    gae_app = os.environ.get('GAE_APPLICATION', '')
    return '~' in gae_app


def project_id():
    """
    Return the real or local project id.
   """
    if detect_gae():
        return os.environ.get('GAE_APPLICATION', '').split('~')[1]
    else:
        return __localdev_project_id()


def gae_url(path):
    assert path[0] != '/'
    return f'https://{gae_svc()}-dot-{project_id()}.{region()}.r.appspot.com/{path}'


def gae_svc():
    ret = os.environ.get('GAE_SERVICE', __local_gae_svc())
    return ret


def get_all_projects() -> typing.List[str]:
    projects = [p for p in resource_manager_client.list_projects()]
    logging.info('Will add labels for %s', sorted(projects))
    return projects


def __localdev_region():
    return 'localregion'


def __local_gae_svc():
    return 'localservice'


def __localdev_project_id():
    return 'joshua-playground2'


def region():
    if detect_gae():
        return os.environ.get('GAE_APPLICATION', '').split('~')[0]
    else:
        return __localdev_region()


def region_from_zone(zone):
    return zone[:len(zone) - 2]


def generate_uuid():
    return str(uuid.uuid4())
