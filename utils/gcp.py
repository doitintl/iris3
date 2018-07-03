from google.auth import app_engine
from googleapiclient import discovery
import logging
credentials = app_engine.Credentials()

service = discovery.build(
    'cloudresourcemanager', 'v1', credentials=credentials)


def get_all_projetcs():
    logging.debug("starting get_all_projetcs")
    request = service.projects().list()
    projects = []
    logging.debug(request)
    while request is not None:
        response = request.execute()
        logging.debug(response)
        if 'projects' in response:
            logging.debug("Found project %s", response['projects'])
            projects.extend(response['projects'])
        request = service.projects().list_next(
            previous_request=request, previous_response=response)
    logging.debug(projects)
    return projects


def get_name_tag():
    return "iris_name"


def get_zone_tag():
    return "iris_zone"


def get_region_tag():
    return "iris_region"


def get_loc_tag():
    return "iris_location"


def region_from_zone(zone):
    return zone[:len(zone) - 2]
