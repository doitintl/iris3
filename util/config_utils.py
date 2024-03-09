import functools
import os
import re
import sys
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


def iris_homepage_text():
    return f"I'm {iris_prefix().capitalize()}, pleased to meet you!"


def specific_prefix(resource_type) -> str:
    config = get_config()
    specific_prefixes = config.get("specific_prefixes", {})
    return specific_prefixes.get(resource_type)


def is_project_enabled(project_id: str) -> bool:
    enabled_projs = enabled_projects()
    if enabled_projs:
        return project_id in enabled_projs
    else:
        return True


def enabled_projects() -> typing.List[str]:
    return get_config().get("projects")


def enabled_plugins() -> typing.List[str]:
    config = get_config()
    plugins = config.get("plugins")

    assert all(re.match(r"[a-z]+", p) for p in plugins), plugins
    return plugins


def is_plugin_enabled(plugin) -> bool:
    plugins = enabled_plugins()
    return (plugin in plugins) if plugins else True


def label_all_on_cron() -> bool:
    config = get_config()
    ret = config.get("label_all_on_cron")
    assert isinstance(ret, bool), ret
    return ret


@functools.lru_cache
def get_config() -> typing.Dict:
    test_config_file = "config-test.yaml"
    prod_config_file = "config.yaml"
    if os.path.isfile(test_config_file):
        config_file_to_use = test_config_file

    else:
        config_file_to_use = prod_config_file

    try:
        with open(config_file_to_use) as f:
            config = yaml.full_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Could not find the needed config file {config_file_to_use}."
            f"You may want to create one, based perhaps on config.yaml.original"
        )
    config["config_file"] = config_file_to_use

    return config


def is_test_configuration():
    return config_test_file() != "config.yaml"


def config_test_file():
    return get_config()["config_file"]
