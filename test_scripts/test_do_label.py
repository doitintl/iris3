import json

from test_scripts.utils_for_tests import do_local_http

project = "joshua-playground-host-vpc"
# plugins = "Buckets,Bigquery,Instances,Disks,Snapshots,Topics,Subscriptions,Cloudsql,Bigtable"
plugins = "Instances,Disks,Snapshots"


def do_label_test():
    for plugin in plugins.split(","):
        contents = json.dumps({"project_id": project, "plugin": plugin})
        do_local_http("do_label", contents)


do_label_test()
