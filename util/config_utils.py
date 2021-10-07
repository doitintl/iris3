import functools
import typing

import yaml


def is_copying_labels_from_project():
    config = __load_config()
    from_project = config.get("from_project")
    assert isinstance(from_project, bool), from_project
    return from_project


def iris_prefix():
    config = __load_config()
    ret = config["iris_prefix"]
    return ret


def is_project_included(project_id):
    projects = included_projects()
    return (project_id in projects) if projects else True


def included_projects():
    config = __load_config()
    projects = config.get("projects")
    return projects


@functools.lru_cache
def __load_config() -> typing.Dict:
    with open("config.yaml", "r") as config_file:
        config = yaml.full_load(config_file)
    return config
