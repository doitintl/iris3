import json
from urllib import request


req = request.Request(
        'http://localhost:5000/do_label?project_id=joshua-playground-host-vpc&plugin=Gce',
        method='POST')
resp = request.urlopen(req)
print(resp.status)
