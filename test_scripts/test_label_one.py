import os
import sys

from plugins.snapshots import Snapshots
from test_scripts.utils_for_tests import label_one
import os

"""

This is a debugging tool  useful in development. It simulates the action that happens when the log sink generates
a PubSub message, when a resource is created.


To use this:
1. Create resources that you want to test, for example a BigQuery Table table-1 in dataset-1.
2. Run main.py in debug mode.
3. Then run this file, test_label_one.py. Error messages will tell you what input it needs, but in summary:
  * Use command line argument "buckets", "cloudsql", or any other of the resource types
    in the test_... functions below. 
  * Give it the environment variables
    - `project` in which where the resource is deployed
    - `resource` for the name of the resource (in a BigQuery example, table-1)
    -  and `parent` for the name of the parent if relevant (in the BigQuery example, dataset-1). 
        The parent is needed only with BigQuery Tables and PubSub Subscriptions.
 
"""


def __project():
    proj = os.environ.get("project")
    if not proj:
        raise ValueError("Must specify 'project' key in environment.")
    return proj


def __resource_name():
    resource = os.environ.get("resource")
    if not resource:
        raise ValueError(
            "Must specify 'resource' key in environment for name of "
            "resource, e.g. the name of the VM Instance, Disk, Subscription, Topic, "
            "BigTable Instance, BigQuery Table or Dataset, "
            "Cloud Storage Bucket, or CloudSQL Instance"
        )
    return resource


def __parent_name():
    parent = os.environ.get("parent")
    if not parent:
        raise ValueError(
            "Must specify 'parent' key in environment for name of parent of the "
            "resource under test, e.g. BigQuery Dataset name for a BigQuery table, "
            "or PubSub Topic for a Subscription"
        )

    return parent


def test_buckets():
    from plugins.buckets import Buckets

    label_one(__project(), __resource_name(), Buckets().method_names()[0])


def test_cloudsql():
    from plugins.cloudsql import Cloudsql

    label_one(__project(), __resource_name(), Cloudsql().method_names()[0])


def test_dataset():
    label_one(__project(), __resource_name(), "datasetservice.insert")


def test_table():
    label_one(__project(), __resource_name(), "tableservice.insert", __parent_name())


def test_instances():
    label_one(__project(), __resource_name(), "compute.instances.insert")


def test_snapshots():
    label_one(__project(), __resource_name(), Snapshots().method_names()[0])


def test_disks():
    from plugins.disks import Disks

    label_one(
        __project(),
        __resource_name(),
        Disks().method_names()[0],
    )


def test_topics():
    from plugins.topics import Topics

    label_one(__project(), __resource_name(), Topics().method_names()[0])


def test_subscriptions():
    from plugins.subscriptions import Subscriptions

    label_one(
        __project(),
        __resource_name(),
        Subscriptions().method_names()[0],
        __parent_name(),
    )


def test_bigtable():
    from plugins.bigtable import Bigtable

    label_one(__project(), __resource_name(), Bigtable().method_names()[0])


def main():
    dir_ = dir(sys.modules[__name__])
    test_func = [f for f in dir_ if f.startswith("test_")]
    test_func_s = ", ".join(sorted(test_func))
    if len(sys.argv) == 1 or (sys.argv[1] == "-h" or sys.argv[1] == "--help"):
        print(
            f"""Usage: {os.path.basename(sys.argv[0])} <RESOURCE_TYPE> 
             where <RESOURCE_TYPE> is any of {test_func_s}
             Environment variables are also needed: project, resource, and in some cases parent. Messages will remind you of required values."""
        )
        exit(1)
    func_name = "test_" + sys.argv[1]
    thismodule = sys.modules[__name__]
    f = getattr(
        thismodule,
        func_name,
    )
    f()


if __name__ == "__main__":
    main()
