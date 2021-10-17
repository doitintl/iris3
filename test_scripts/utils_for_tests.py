import base64
import json
import logging
import os
import typing
from string import Template
from textwrap import shorten
from urllib import request
from urllib.parse import urlencode

from util.config_utils import pubsub_token

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)

LOCAL_PORT = 8000


def __datastruct_for_pubsub_message(contents: str) -> bytes:
    encoded = base64.b64encode(contents.encode("utf-8"))
    encoded_data = {"data": encoded.decode("utf-8")}
    envelope = {"message": encoded_data}
    data_str = json.dumps(envelope)
    return data_str.encode("utf-8")


def do_local_http(
        path: str,
        contents: typing.Optional[str] = None,
        method="POST",
        headers: typing.Optional[typing.Dict[str, str]] = None,
        extra_args=None,
):
    headers = headers or {}
    data_bytes = __datastruct_for_pubsub_message(contents) if contents else None

    logging.info(f"Will call {path} sending {contents}")
    host_and_port = f"localhost:{LOCAL_PORT}"
    args_s = ""
    if extra_args:
        args_s = "&"
        args_s += urlencode(extra_args)
    req = request.Request(
        f"http://{host_and_port}/{path}?token={pubsub_token()}{args_s}",
        data=data_bytes,
        method=method,
    )
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    resp = request.urlopen(req)  # Exception if Status >=300
    assert resp.status < 300, resp.status
    logging.info("OK for %s: %s", path, shorten(str(contents), 150))


def label_one(project, name, method_name, parent_name="", extra_args=None):
    ls = os.listdir(".")
    if "sample_data" not in ls:
        raise ValueError("Run script in project root")

    with open(f"./sample_data/{method_name}.log_message.json") as f:
        file_contents = f.read()
        temp_obj = Template(file_contents)
        json_s = temp_obj.substitute(
            project=project, name=name, parent_name=parent_name
        )
        do_local_http("label_one", json_s, extra_args=extra_args)
