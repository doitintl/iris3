from test_scripts.integ_test_base import BaseIntegTest


class FewTypeIntegTest(BaseIntegTest):
    @staticmethod
    def _resource_description_commands(gce_zone, run_id, test_project):
        describe_flags = f"--project {test_project} --format json"
        for idx in range(2):
            commands = [
                f"gcloud pubsub topics describe topic{run_id}{idx} {describe_flags}",
                f"gcloud pubsub subscriptions describe subscription{run_id}{idx} {describe_flags}",
            ]
            return commands

    @staticmethod
    def _resource_deletion_commands(gce_zone, resources_project, run_id):
        for idx in range(2):
            commands = [
                f"gcloud pubsub topics delete -q topic{run_id}{idx} --project {resources_project}",
                f"gcloud pubsub subscriptions -q delete subscription{run_id}{idx} --project {resources_project}",
            ]
            return commands

    @staticmethod
    def _resource_creation_commands(gce_zone, run_id, test_project):
        for idx in range(2):
            commands = [  # Some must be run sequentially, and so are in list form
                [
                    f"gcloud pubsub topics create topic{run_id}{idx} --project {test_project}",
                    f"gcloud pubsub subscriptions create subscription{run_id}{idx} --topic topic{run_id} --project {test_project}",
                ],
            ]
            return commands
