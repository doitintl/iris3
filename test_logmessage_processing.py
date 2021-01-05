import json
from urllib import request

with open('./sample_data/sample_insert_instance_log_message.json') as f:
    contents = f.read()
    j = json.loads(contents)

    data_str = json.dumps(j)
    data_bytes = data_str.encode('utf-8')
    req = request.Request('http://localhost:5000/label_one_from_logline', data=data_bytes)
    req.add_header('Content-Type', 'application/json')
    resp = request.urlopen(req)
    print(resp.status)
