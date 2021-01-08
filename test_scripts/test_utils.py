import base64
import json
import logging
import typing
from urllib import request

from util.config_utils import pubsub_token


def __datastruct_for_pubsub_message(contents: str) -> bytes:
    encoded = base64.b64encode(contents.encode('utf-8'))
    encoded_data = {'data': encoded.decode('utf-8')}
    envelope = {'message': encoded_data}
    data_str = json.dumps(envelope)
    return data_str.encode('utf-8')


def do_local_http(path: str, contents: typing.Optional[str], method='POST'):
    data_bytes = __datastruct_for_pubsub_message(contents)
    host_and_port = 'localhost:5000'
    req = request.Request(f'http://{host_and_port}/{path}?{pubsub_token()}', data=data_bytes,
                          method=method)
    req.add_header('Content-Type', 'application/json')
    resp = request.urlopen(req)
    logging.info(resp.status)
    if resp.status > 299:
        raise ValueError(resp.status)
