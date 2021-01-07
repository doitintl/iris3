import logging
import os
import typing
import uuid

from google.cloud import resource_manager

from util import localdev_config

resource_manager_client = resource_manager.Client()


def detect_gae():
    gae_app = os.environ.get('GAE_APPLICATION', '')
    return '~' in gae_app


def project_id():
    """
    :return the project id on which we run AppEngine and PubSub
    """
    if detect_gae():
        return os.environ.get('GAE_APPLICATION', '').split('~')[1]
    else:
        return localdev_config.localdev_project_id()


def set_project_env_if_needed():
    if not detect_gae():
        localdev_config.set_localdev_project_id_in_env()


# def gae_url(path=''):
#    assert not path or path[0] != '/', path
#    gae_region_code = gae_region_abbreviation()
#    ret = f'https://{gae_svc()}-dot-{project_id()}.{gae_region_code}.r.appspot.com/{path}'
#    return ret


def gae_svc():
    ret = os.environ.get('GAE_SERVICE', localdev_config.local_gae_svc())
    return ret


def get_all_projects() -> typing.List[str]:
    projects = [p.project_id for p in resource_manager_client.list_projects()]
    projects.sort()
    if localdev_config.localdev_projects():
        projects = list(filter(lambda p: p in localdev_config.localdev_projects(), projects))
    logging.info('%s projects: %s ', len(projects), projects[:100])
    return projects


# def gae_region_abbreviation():
#    return 'uc'


def region_from_zone(zone):
    return zone[:len(zone) - 2]


def generate_uuid() -> str:
    """:return a UUID as a string (and not an object or bytes; this is required
    by the http API. """
    return str(uuid.uuid4())
