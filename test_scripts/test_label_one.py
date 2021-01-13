
from test_scripts.utils_for_tests import label_one

project = "joshua-playground-host-vpc"


# TODO Test label_one for disks, snapshots, topics, bigtable
def test_bucket():
    from alt_plugins.buckets import Buckets

    label_one(project, "b89712398", Buckets().method_names()[0])


def test_cloudsql():
    from alt_plugins.cloudsql import Cloudsql

    label_one(
        project, "myinstance2", Cloudsql().method_names()[0],
        extra_args={"override_on_demand": "true"},
    )


def test_dataset():
    label_one(project, "dataset3", "datasetservice.insert")


def test_instance():
    label_one(
        project, "instance-small", "compute.instances.insert"
    )


def test_table():
    label_one(project, "table3", "tableservice.insert", "dataset3")


def test_subscription():
    from alt_plugins.subscriptions import Subscriptions

    label_one(
        project, "sub1", Subscriptions().method_names()[0], "topic1",
    )


def test_topic():
    from plugins.topics import Topics
    label_one( project, "topic2", Topics().method_names()[0] )
