import base64
import json
import logging
import typing
import urllib
from urllib import request

from util.gcp_utils import pubsub_token

LOCAL_PORT=8000

def __datastruct_for_pubsub_message(contents: str) -> bytes:
    encoded = base64.b64encode(contents.encode('utf-8'))
    encoded_data = {'data': encoded.decode('utf-8')}
    envelope = {'message': encoded_data}
    data_str = json.dumps(envelope)
    return data_str.encode('utf-8')


def do_local_http(path: str, contents: typing.Optional[str], method='POST', headers:typing.Optional[typing.Dict[str,str]]=None):
    headers=headers or {}
    data_bytes = __datastruct_for_pubsub_message(contents) if contents else None
    host_and_port = 'localhost:%s'% LOCAL_PORT
    req = request.Request(f'http://{host_and_port}/{path}?token={pubsub_token()}', data=data_bytes,
                          method=method)
    req.add_header('Content-Type', 'application/json')
    for k,v in headers.items():
        req.add_header(k,v)
    resp = request.urlopen(req) #Exception if Status >=300
    assert resp.status<300, resp.status
    logging.info('OK for %s', path)

