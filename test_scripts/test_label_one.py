from test_scripts.test_utils import do_local_http

with open('../sample_data/sample_insert_instance_log_message.json') as f:
    do_local_http(f.read(), 'label_one')
