import json
import os
import sys

from test_scripts.utils_for_tests import do_local_http

"""
This is a debugging tool useful in development.
It simulates the action that happens in response to a Cloud Scheduler call to /schedule.

To use it.
1. Run main.py in debug mode
2, Comment out any of the plugins that you do not want to test (see below)
3. Then run this file, test_do_label.py, specifying the project in the environment,
and optionally a comma-separated list of  resource types selected from PLUGINS (below to focus the testing
on these types.
"""
PLUGINS = [
    "Buckets",
    "Bigquery",
    "Instances",
    "Disks",
    "Snapshots",
    "Topics",
    "Subscriptions",
    "Cloudsql",
    "Bigtable",
]


def test_do_label(chosen_plugins):
    project = __project()

    for plugin in chosen_plugins:
        contents = json.dumps({"project_id": project, "plugin": plugin})
        do_local_http("do_label", contents)


def __project():
    proj = os.environ.get("project")
    if not proj:
        raise ValueError("Must specify 'project' key in environment.")
    return proj


def main():
    if len(sys.argv) > 1 and (sys.argv[1] == "-h" or sys.argv[1] == "--help"):
        print(
            f"""Usage: {os.path.basename(sys.argv[0])} [<RESOURCE_TYPES> ]
             where <RESOURCE_TYPES> is a comma-separated list selected from {",".join(PLUGINS)} 
             Also set environment key project with GCP project-ID
             """
        )
        exit(1)
    msg = ""
    if len(sys.argv) == 1:
        chosen_plugins = PLUGINS
        msg = " all plugins"
    else:
        plugins_s = sys.argv[1]
        chosen_plugins = plugins_s.split(",")
        chosen_plugins = [s.strip() for s in chosen_plugins]
        unsupported = [p for p in chosen_plugins if p not in PLUGINS]
        if unsupported:
            raise Exception(f"Unsupported: {', '.join(unsupported)}")
    print(f"Will do_label on{msg}: {', '.join(chosen_plugins)} ")
    test_do_label(chosen_plugins)


if __name__ == "__main__":
    main()
