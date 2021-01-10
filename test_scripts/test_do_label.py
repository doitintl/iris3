import json
import logging
import sys

from test_scripts.utils_for_tests import do_local_http

project = 'joshua-playground-host-vpc'
plugins = 'Bigtable'
#plugins = 'BigtableGcs,BigQuery,Instances,Disks,Snapshots'

for plugin in plugins.split(','):
    contents = json.dumps({'project_id': project, 'plugin': plugin})
    do_local_http('do_label', contents)
