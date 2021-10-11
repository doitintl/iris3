import os
import sys

from plugins.snapshots import Snapshots
from test_scripts.utils_for_tests import label_one

"""

This is a debugging tool  useful in development. It simulates the action that happens when the log sink generates
a PubSub message, when a resource is created.


To use this:
1. Create resources that you want to test, for example a BigQuery Table table-1 in dataset-1.
2. Run main.py in debug mode.
3. Then run this file (in project root), test_label_one.py. Error messages will tell you what input it needs, but in summary:
   
  * Give it the environment variables
    - `resource_type` selected from "buckets", "cloudsql", or any other of the 
        resource types in the test_... functions below
    - `project` where the resource is deployed
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
    test_ = "test_"
    test_func = [f for f in dir_ if f.startswith(test_)]
    resource_types = [f[len(test_):] for f in test_func]
    resource_types_s = ", ".join(sorted(resource_types))
    resource_type = os.environ.get("resource_type", "")
    func_name = test_ + resource_type
    if (
            func_name not in dir_
            or not resource_type
            or len(sys.argv) > 1
            and (sys.argv[1] == "-h" or sys.argv[1] == "--help")
    ):
        print(
            f"""Usage: {os.path.basename(sys.argv[0])}  
             Environment variables are needed:
             - resource_type, selected from {resource_types_s} 
             - project where the resource is deployed
             - resource for the name of the resource (for example, a BigQuery table called table-1 )
             - parent for the name of the parent if relevant (in the BigQuery example, dataset-1). 
                The parent is needed only with BigQuery Tables and PubSub Subscriptions.
            """
        )
        exit(1)

    f = getattr(
        sys.modules[__name__],
        func_name,
    )
    f()


if __name__ == "__main__":
    main()
