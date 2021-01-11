import functools
import json

import typing


def get_labels():
    config = __load_config()
    return config['labels']


def iris_prefix():
    return 'iris'


# Py3.9 has functools.cache
@functools.lru_cache
def __load_config() -> typing.Dict:
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
    return config
