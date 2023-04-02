import functools
import logging
import os
import re
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


def specific_prefix(resource_type) -> str:
    config = get_config()
    specific_prefixes = config.get("specific_prefixes", {})
    return specific_prefixes.get(resource_type)


def is_project_enabled(project_id) -> bool:
    projects = enabled_projects()
    return (project_id in projects) if projects else True


def enabled_projects() -> typing.List[str]:
    config = get_config()
    projects = config.get("projects")
    return projects


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


def pubsub_token() -> str:
    config = get_config()
    return config.get("pubsub_verification_token")


@functools.lru_cache
def get_config() -> typing.Dict:
    test_config = "config-test.yaml"
    dev_config = "config-dev.yaml"

    if os.path.isfile(test_config):
        config_filename = test_config
        logging.info("Using test configuration")
    elif os.path.isfile(dev_config):
        config_filename = dev_config
        logging.info("Using dev configuration")
    else:
        logging.info("Using projection configuration")
        config_filename = "config.yaml"

    with open(config_filename) as config_file:
        config = yaml.full_load(config_file)
    return config
