import json
import os
import sys

from test_scripts.utils_for_tests import do_local_http
from util.utils import log_time

"""
This is a debugging tool useful in development.
It simulates the action that happens in response to a Cloud Scheduler call to /schedule.

To use it.
1. Run main.py in debug mode
2. Then run this file (in project root). See Usage below (or run test_do_label.py --help)
"""
PLUGINS = [
    "Buckets",
    "Bigquery",
    "Bigtable",
    "Cloudsql",
    "Disks",
    "Instances",
    "Snapshots",
    "Subscriptions",
    "Topics",
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

@log_time
def main():
    if len(sys.argv) > 1 and (sys.argv[1] == "-h" or sys.argv[1] == "--help"):
        print(
            f"""Usage: {os.path.basename(sys.argv[0])} 
             Set environment with
             - required key project with GCP project-ID 
             - optional key plugins with a comma-separated list selected from {",".join(PLUGINS)} 
               (default is to run all plugins)
             - optional key LOCAL_PORT for the port of the local Iris server
             """
        )
        exit(1)
    msg = ""
    plugins_s = os.environ.get("plugins")
    if not plugins_s:
        chosen_plugins = PLUGINS
        msg = " all plugins"
    else:
        chosen_plugins = plugins_s.split(",")
        chosen_plugins = [s.strip() for s in chosen_plugins]
        unsupported = [p for p in chosen_plugins if p not in PLUGINS]
        if unsupported:
            raise Exception(f"Error: \"{', '.join(unsupported)}\" not a legal value. "
                            f"For this test, you can use these (comma-separated) in the env variable: {PLUGINS}")
    print(f"Will do_label on{msg}: {', '.join(chosen_plugins)} ")
    test_do_label(chosen_plugins)


if __name__ == "__main__":
    main()
