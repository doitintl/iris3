import base64
import json
from urllib import request

with open('../sample_data/sample_insert_instance_log_message.json') as f:
    contents = f.read()
    encoded=    base64.b64encode(contents.encode('utf-8'))
    encoded_data = {'data': encoded.decode('utf-8')}
    envelope={'message': encoded_data}
    data_str = json.dumps(envelope)
    data_bytes = data_str.encode('utf-8')
    req = request.Request('http://localhost:5000/label_one', data=data_bytes)
    req.add_header('Content-Type', 'application/json')
    resp = request.urlopen(req)
    print(resp.status)
