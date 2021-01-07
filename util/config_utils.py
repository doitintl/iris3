import json

import typing


def get_labels():
    config = __load_config()
    return config['labels']


# TODO: ondemand should be a boolean value per-plugin. This code instead attaches the
# whole list of on-demand plugin_classes to *each* plugin class.
def get_ondemand() -> typing.List[str]:
    config = __load_config()
    return config['on_demand']


def iris_prefix():
    return 'iris'


def __load_config():
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
    return config
