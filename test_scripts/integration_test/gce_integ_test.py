import operator
from functools import reduce
from typing import List, Union

from test_scripts.integration_test.integ_test_base import BaseIntegTest
from util.gcp.gcp_utils import region_from_zone


class GCEIntegTest(BaseIntegTest):
    def __init__(self):
        super().__init__()
        loops = 2
        self.__sfxs = ["number" + str(i) for i in range(loops)]

    def _resource_description_commands(
        self,
        gce_zone,
        run_id,
        test_project,
    ) -> List[str]:
        describe_flags = f"--project {test_project} --format json"
        cmdlists = [
            [
                f"gcloud compute instances describe instance{run_id}{sfx} --zone {gce_zone} {describe_flags}",
                f"gcloud compute disks describe disk{run_id}{sfx} --zone {gce_zone} {describe_flags}",
                f"gcloud compute snapshots describe snapshot{run_id}{sfx} {describe_flags}",
            ]
            for sfx in self.__sfxs
        ]
        return list(reduce(operator.concat, cmdlists))

    def _resource_deletion_commands(
        self, gce_zone, resources_project, run_id
    ) -> List[str]:
        cmdlists = [
            [
                f"gcloud compute instances delete -q instance{run_id}{sfx} --project {resources_project} --zone {gce_zone}",
                f"gcloud compute snapshots delete -q snapshot{run_id}{sfx} --project {resources_project}",
                f"gcloud compute disks delete -q disk{run_id}{sfx} --project {resources_project} --zone {gce_zone}",
                f"gcloud compute instances delete -q instance{run_id}{sfx} --project {resources_project} --zone {gce_zone}",
                f"gcloud compute snapshots delete -q snapshot{run_id}{sfx} --project {resources_project}",
                f"gcloud compute disks delete -q disk{run_id}{sfx} --project {resources_project} --zone {gce_zone}",
            ]
            for sfx in self.__sfxs
        ]

        return list(reduce(operator.concat, cmdlists))

    def _resource_creation_commands(
        self, gce_zone, run_id, test_project
    ) -> List[Union[List[str], str]]:
        region = region_from_zone(gce_zone)
        # Some must be run sequentially, and so are bundled into lists
        return [
            [
                f"gcloud compute disks create disk{run_id}{sfx} --project {test_project} --zone {gce_zone}",
                f"gcloud compute snapshots create snapshot{run_id}{sfx} --source-disk disk{run_id} --source-disk-zone {gce_zone} --storage-location {region} --project {test_project}",
            ]
            for sfx in self.__sfxs
        ] + [
            f"gcloud compute instances create instance{run_id}{sfx} --project {test_project} --zone {gce_zone}"
            for sfx in self.__sfxs
        ]
