from plugins.snapshots import Snapshots
from test_scripts.utils_for_tests import label_one

project = "joshua-playground-host-vpc"


def test_buckets():
    from plugins.buckets import Buckets

    label_one(project, "b89712398", Buckets().method_names()[0])


def test_cloudsql():
    from plugins.cloudsql import Cloudsql

    label_one( project, "myinstance2", Cloudsql().method_names()[0], extra_args={"override_on_demand": "true"}, )


def test_dataset():
    label_one(project, "dataset3", "datasetservice.insert")

def test_instances():
    label_one(project, "instance-small", "compute.instances.insert")

def test_snapshots():
    label_one(project, "instance1", Snapshots().method_names()[0])



def test_table():
    label_one(project, "table3", "tableservice.insert", "dataset3")


def test_subscriptions():
    from plugins.subscriptions import Subscriptions

    label_one( project, "sub1", Subscriptions().method_names()[0], "topic1" )


def test_disks():
    from plugins.disks import  Disks

    label_one( project, "disk1", Disks().method_names()[0],  )

def test_topics():
    from plugins.topics import Topics

    label_one(project, "topic2", Topics().method_names()[0])

def test_bigtable():
    from plugins.bigtable import Bigtable

    label_one(project, "instance1", Bigtable().method_names()[0])
