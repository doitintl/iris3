import functools
import typing

import yaml


def possible_label_keys():
    config = __load_config()
    return config["labels"]


def is_copying_labels_from_project():
    config = __load_config()
    from_project_ = config.get("from_project")
    assert isinstance(from_project_, bool)
    return from_project_


def iris_label_key_prefix():
    config = __load_config()
    return config["iris_prefix"]


def is_project_included(project_id):
    config = __load_config()
    projects = config.get("projects")
    if not projects:  # No filter
        return True
    else:
        return project_id in projects


# Py3.9 has functools.cache
@functools.lru_cache
def __load_config() -> typing.Dict:
    with open("config.yaml", "r") as config_file:
        config = yaml.full_load(config_file)
    return config

