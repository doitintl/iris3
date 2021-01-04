import json

import typing


def get_labels():
    config = __load_config()
    return config['labels']


def __load_config():
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
    return config


def __load_dev_config():
    with open('dev_config.json', 'r') as config_file:
        config = json.load(config_file)
    return config

#TODO: ondemand should be a boolean value per-plugin. Instead, we attach
# the whole list of on-demand plugins to each plugin./
def get_ondemand()->typing.List:
    config = __load_config()
    return config['on_demand']


def get_iris_prefix():
    return 'iris'