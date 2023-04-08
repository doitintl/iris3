import functools
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


def pubsub_token() -> str:
    config = get_config()
    return config.get("pubsub_verification_token")


@functools.lru_cache
def get_config() -> typing.Dict:
    dev_config = "config-dev.yaml"
    test_config = "config-test.yaml"
    prod_config = "config.yaml"

    if os.path.isfile(dev_config):
        config_name = dev_config
        is_test_or_dev_ = True
    elif os.path.isfile(test_config):
        config_name = test_config
        is_test_or_dev_ = True
    else:
        config_name = prod_config
        is_test_or_dev_ = False
    print("Using", config_name)  # logging not yet enabled
    with open(config_name) as config_file:
        config = yaml.full_load(config_file)
    config["is_test_or_dev_configuration"] = is_test_or_dev_
    return config


def is_test_or_dev_configuration():
    return get_config()["is_test_or_dev_configuration"]


def is_in_test_or_dev_project(project_id):

    markers = get_config().get("test_or_dev_project_markers", [])
    for marker in markers:
        if marker and marker in project_id:
            return True
    return False
