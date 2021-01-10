import json

import typing


def get_labels():
    config = __load_config()
    return config['labels']

#TOD This boolean should just be a hardcoded class member, not in the JSON
# whole list of on-demand subclasses to *each* plugin class.
def on_demand_plugins() -> typing.List[str]:
    config = __load_config()
    return config['on_demand']


def iris_prefix():
    return 'iris'


def __load_config():
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
    return config
