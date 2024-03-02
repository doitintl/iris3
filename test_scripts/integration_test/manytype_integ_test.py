from typing import List, Union

from test_scripts.integration_test.integ_test_base import BaseIntegTest
from util.gcp.gcp_utils import region_from_zone


class ManyTypeIntegTest(BaseIntegTest):
    def _resource_description_commands(
        self, gce_zone, run_id, test_project
    ) -> List[str]:
        describe_flags = f"--project {test_project} --format json"
        commands = [
            f"gcloud pubsub topics describe topic{run_id} {describe_flags}",
            f"gcloud pubsub subscriptions describe subscription{run_id} {describe_flags}",
            f"bq show --format=json {test_project}:dataset{run_id}",
            f"bq show --format=json {test_project}:dataset{run_id}.table{run_id}",
            f"gcloud compute instances describe instance{run_id} --zone {gce_zone} {describe_flags}",
            f"gcloud compute disks describe disk{run_id} --zone {gce_zone} {describe_flags}",
            f"gcloud compute snapshots describe snapshot{run_id} {describe_flags}",
            f"gsutil label get gs://bucket{run_id}",
        ]
        return commands

    def _resource_deletion_commands(
        self, gce_zone, resources_project, run_id
    ) -> List[Union[List[str], str]]:
        commands = [
            f"gcloud compute instances delete -q instance{run_id} --project {resources_project} --zone {gce_zone}",
            f"gcloud compute snapshots delete -q snapshot{run_id} --project {resources_project}",
            f"gcloud compute disks delete -q disk{run_id} --project {resources_project} --zone {gce_zone}",
            f"gcloud pubsub topics delete -q topic{run_id} --project {resources_project}",
            f"gcloud pubsub subscriptions -q delete subscription{run_id} --project {resources_project}",
            [
                f"bq rm -f --table {resources_project}:dataset{run_id}.table{run_id}",
                f"bq rm -f --dataset {resources_project}:dataset{run_id}",
            ],
            f"gsutil rm -r gs://bucket{run_id}",
        ]
        return commands

    def _resource_creation_commands(
        self, gce_zone, run_id, test_project
    ) -> List[Union[List[str], str]]:
        region = region_from_zone(gce_zone)
        commands = [  # Some must be run sequentially, and so are in list form
            f"gcloud compute instances create instance{run_id} --project {test_project} --zone {gce_zone}",
            [
                f"gcloud compute disks create disk{run_id} --project {test_project} --zone {gce_zone}",
                f"gcloud compute snapshots create snapshot{run_id} --source-disk disk{run_id} --source-disk-zone {gce_zone} --storage-location {region} --project {test_project}",
            ],
            [
                f"gcloud pubsub topics create topic{run_id} --project {test_project}",
                f"gcloud pubsub subscriptions create subscription{run_id} --topic topic{run_id} --project {test_project}",
            ],
            [
                f"bq mk --dataset {test_project}:dataset{run_id}",
                f"bq mk --table {test_project}:dataset{run_id}.table{run_id}",
            ],
            f"gsutil mb -p {test_project} gs://bucket{run_id}",
        ]
        return commands
