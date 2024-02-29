import itertools
from typing import List, Union

from test_scripts.integration_test.integ_test_base import BaseIntegTest


class FewTypeIntegTest(BaseIntegTest):
    def __init__(self):
        super().__init__()
        loops = 5
        self.sfxs = ["number" + str(i) for i in range(loops)]
        pass

    def _resource_creation_commands(self, gce_zone, run_id, test_project)-> List[Union[List[str], str]]:
        # Some must be run sequentially, and so are in list form

        return [
            [
                f"gcloud pubsub topics create topic{run_id}{sfx} --project {test_project}",
                f"gcloud pubsub subscriptions create subscription{run_id}{sfx} --topic topic{run_id}{sfx} --project {test_project}",
            ]
            for sfx in self.sfxs
        ]

    def _resource_description_commands(self, gce_zone, run_id, test_project)->List[str]:
        describe_flags = f"--project {test_project} --format json"
        cmdlists= [
            [
                f"gcloud pubsub topics describe topic{run_id}{sfx} {describe_flags}",
                f"gcloud pubsub subscriptions describe subscription{run_id}{sfx} {describe_flags}",
            ]
            for sfx in self.sfxs
        ]
        return list(itertools.chain(cmdlists))

    def _resource_deletion_commands(self, gce_zone, resources_project, run_id)-> List[Union[List[str], str]]:
        return [
            [
                f"gcloud pubsub topics delete -q topic{run_id}{sfx} --project {resources_project}",
                f"gcloud pubsub subscriptions -q delete subscription{run_id}{sfx} --project {resources_project}",
            ]
            for sfx in self.sfxs
        ]
