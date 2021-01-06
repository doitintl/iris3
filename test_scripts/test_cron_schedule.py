import json
from urllib import request

with open('sample_data/sample_insert_instance_log_message.json') as f:

    req = request.Request('http://localhost:5000/schedule', method='GET')
    resp = request.urlopen(req)
    print(resp.status)
