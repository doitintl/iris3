import json

from test_scripts.test_utils import do_local_http

contents = {'project_id': 'joshua-playground-host-vpc', 'plugin': 'Gce'}
contents_s = json.dumps(contents)

with open('../sample_data/sample_insert_instance_log_message.json') as f:
    do_local_http(contents_s, 'do_label')
