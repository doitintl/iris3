import json
import logging
import sys

from test_scripts.utils_for_tests import do_local_http

if len(sys.argv) > 1:
    project = sys.argv[1]
    plugins = sys.argv[2]
else:
    project = 'joshua-playground-host-vpc'
    plugins = 'Instances,Disks'
    #plugins = 'Gcs,BigQuery,Instances,Disks,Snapshots'

for plugin in plugins.split(','):
    contents = json.dumps({'project_id': project, 'plugin': plugin})
    do_local_http('do_label', contents)
