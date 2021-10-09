import functools
import typing

import yaml


def is_copying_labels_from_project() -> bool:
    config = __load_config()
    from_project = config.get("from_project")
    assert isinstance(from_project, bool), from_project
    return from_project


def iris_prefix() -> str:
    config = __load_config()
    ret = config["iris_prefix"]
    return ret


def configured_project(project_id) -> bool:
    projects = configured_projects()
    return (project_id in projects) if projects else True


def configured_projects() -> typing.List[str]:
    config = __load_config()
    projects = config.get("projects")
    return projects


def label_all_on_cron() -> bool:
    config = __load_config()
    label_all_on_cron = config.get("label_all_on_cron")
    assert isinstance(label_all_on_cron, bool), label_all_on_cron
    return label_all_on_cron


@functools.lru_cache
def __load_config() -> typing.Dict:
    with open("config.yaml", "r") as config_file:
        config = yaml.full_load(config_file)
    return config

