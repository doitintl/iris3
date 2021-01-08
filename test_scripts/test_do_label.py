import json

from test_scripts.test_utils import do_local_http

contents = json.dumps( {
        'project_id': 'joshua-playground-host-vpc',
        'plugin': 'Gce'
    })

do_local_http('do_label', contents)
