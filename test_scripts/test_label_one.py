from plugins.snapshots import Snapshots
from test_scripts.utils_for_tests import label_one
import os

"""
This integration test simulates the action that happens when the log sink generates
a PubSub message, when a resource is created.

It is useful in development.
* Create resources that you want to test, for example a BigQuery Table table-1 in dataset-1.
* Run main.py in debug mode.
* Run  test_label_one.py with environment variables 
    - `project` where the resource is deployed
    - `instance` for the name of the resource (in this example table-1)
    -  and `parent` for the name of the parent if relevant (in this case dataset-1). 
        The parent is needed only with BigQuery Tables and PubSub Subscriptions.
  
"""


def __project():
    proj = os.environ.get("project")
    if not proj:
        raise ValueError("Must specify 'project' key in environment.")
    return proj


def __instance_name():
    instance = os.environ.get("instance")
    if not instance:
        raise ValueError(
            "Must specify 'instance' key in environment for name of "
            "resource, e.g. GCE VM Instance, Disk, Subscription, Topic, "
            "BigTable Instance, BigQuery Table or Dataset, "
            "Cloud Storage Bucket, or CloudSQL Instance"
        )
    if os.environ.get("use_base_name"):
        return instance
    else:
      return instance+__project()


def __parent_name():
    parent = os.environ.get("parent")
    if not parent:
        raise ValueError(
            "Must specify 'parent' key in environment for name of parent of the "
            "resource under test, e.g. BigQuery Dataset name for a BigQuery table, "
            "or PubSub Topic for a Subscription"
        )
    if os.environ.get("use_base_name"):
        return parent
    else:
      return parent+__project()


def test_buckets():

    from plugins.buckets import Buckets

    label_one(__project(), __instance_name(), Buckets().method_names()[0])


def test_cloudsql():
    from plugins.cloudsql import Cloudsql

    label_one(__project(), __instance_name(), Cloudsql().method_names()[0])


def test_dataset():
    label_one(__project(), __instance_name(), "datasetservice.insert")


def test_table():
    label_one(__project(), __instance_name(), "tableservice.insert", __parent_name())


def test_instances():
    label_one(__project(), __instance_name(), "compute.instances.insert")


def test_snapshots():
    label_one(__project(), __instance_name(), Snapshots().method_names()[0])


def test_disks():
    from plugins.disks import Disks

    label_one(
        __project(),
        __instance_name(),
        Disks().method_names()[0],
    )


def test_topics():
    from plugins.topics import Topics

    label_one(__project(), __instance_name(), Topics().method_names()[0])


def test_subscriptions():
    from plugins.subscriptions import Subscriptions

    label_one(
        __project(),
        __instance_name(),
        Subscriptions().method_names()[0],
        __parent_name(),
    )


def test_bigtable():
    from plugins.bigtable import Bigtable

    label_one(__project(), __instance_name(), Bigtable().method_names()[0])
