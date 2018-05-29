import logging

from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

credentials = GoogleCredentials.get_application_default()

service = discovery.build(
    'cloudresourcemanager', 'v1', credentials=credentials)


def get_all_projetcs():
    request = service.projects().list()
    projects = []
    while request is not None:
        response = request.execute()
        if 'projects' in response:
            projects.extend(response['projects'])
        request = service.projects().list_next(
            previous_request=request, previous_response=response)
    return projects
