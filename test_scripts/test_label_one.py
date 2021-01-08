import sys
from string import Template

from test_scripts.utils_for_tests import do_local_http

with open('./sample_data/sample_insert_instance_log_message.json') as f:
    file_contents=f.read()
    temp_obj = Template(file_contents)
    json_s=temp_obj.substitute(instance='instance-small', project=sys.argv[1])
    do_local_http('label_one', json_s)
