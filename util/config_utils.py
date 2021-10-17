import functools
import typing

import yaml


def is_copying_labels_from_project() -> bool:
    config = get_config()
    from_project = config.get("from_project")
    assert isinstance(from_project, bool), from_project
    return from_project


def iris_prefix() -> str:
    config = get_config()
    return config["iris_prefix"]


def configured_project(project_id) -> bool:
    projects = configured_projects()
    return (project_id in projects) if projects else True


def configured_projects() -> typing.List[str]:
    config = get_config()
    projects = config.get("projects")
    return projects


def label_all_on_cron() -> bool:
    config = get_config()
    ret = config.get("label_all_on_cron")
    assert isinstance(ret, bool), ret
    return ret


def pubsub_token() -> str:
    config = get_config()
    return config.get("pubsub_verification_token")


@functools.lru_cache
def get_config() -> typing.Dict:
    with open("config.yaml") as config_file:
        config = yaml.full_load(config_file)
    return config
