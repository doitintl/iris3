import atexit
import datetime
import json
import logging
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from subprocess import CalledProcessError
from typing import Union, List

from util.utils import random_str, random_hex_str, run_command

config_test_yaml = "config-test.yaml"

failing = False


def set_failing(f):
    global failing
    failing = f


def run_command_or_commands_catch_exc(command_or_commands: Union[str, List[str]]):
    def run_cmd_catch_exc(cmd):
        try:
            return run_command(cmd)
        except CalledProcessError as e:
            logging.exception(f"Calling {cmd}")
            return e

    if isinstance(command_or_commands, str):
        command = command_or_commands
        return run_cmd_catch_exc(command)
    else:
        ret = []
        for command in command_or_commands:
            one_return_value = run_cmd_catch_exc(command)
            if isinstance(one_return_value, Exception):
                return one_return_value  # Return only the exception on first failure
            else:
                ret.append(one_return_value)

        return ret


def describe_resources(run_id, test_project, gce_zone):
    describe_flags = "--project {test_project} --format json"
    commands = [
        f"gcloud pubsub topics describe topic{run_id} {describe_flags}",
        f"gcloud pubsub subscriptions describe subscription{run_id} {describe_flags}",
        f"bq show --format=json {test_project}:dataset{run_id}",
        f"bq show --format=json {test_project}:dataset{run_id}.table{run_id}",
        f"gcloud compute instances describe instance{run_id} --zone {gce_zone} {describe_flags}",
        f"gcloud compute disks describe disk{run_id} --zone {gce_zone} {describe_flags}",
        f"gcloud compute snapshots describe snapshot{run_id} {describe_flags}",
    ]
    with ThreadPoolExecutor() as executor:
        zipped = zip(
            commands, executor.map(run_command_or_commands_catch_exc, commands)
        )
        failed = [cmd for cmd, result in zipped if isinstance(result, Exception)]
        succeeded = {
            cmd: result for cmd, result in zipped if not isinstance(result, Exception)
        }
    if failed:
        print("Failed ", failed)
        set_failing(True)
        sys.exit(1)

    else:
        no_labels = []
        for cmd, result in succeeded.items():
            j = json.loads(result)
            label = j["labels"]
            label_val = label.get([f"{run_id}_name"])
            if not label_val:
                no_labels.append(cmd)
        if no_labels:
            print("no labels", no_labels)
            set_failing(True)
            sys.exit(1)

    gcs_cmd = f"gsutil label get gs://bucket{run_id }"
    out = run_command_or_commands_catch_exc(gcs_cmd)
    if isinstance(out, Exception):
        print("Failed ", gcs_cmd)
        set_failing(True)
        sys.exit(1)

    else:
        assert isinstance(out, str), type(out)
        j = json.loads(out)
        # In GCS, no "labels" wrapper for the actual label
        # Also, for a test of labels that are specific to a resource type,
        # bucket labels start "gcs"
        label_val = j.get([f"gcs{run_id}_name"])
        if not label_val:
            print("GCS failed")
            set_failing(True)
            sys.exit(1)


def main():
    start_test = time.time()
    check_enough_command_line_params()
    run_id = get_run_id()
    check_legal_run_id(run_id)
    deployment_project = sys.argv[1]
    test_project = sys.argv[2]

    # pubsub_test_token is used for envsubst into config.yaml.test.template
    pubsub_test_token = random_hex_str(20)
    gce_zone = "europe-central2-b"

    check_projects_exist(deployment_project, test_project)
    _ = run_command(f"gcloud config set project {test_project}")
    remove_config_file()
    # atexit.register(remove_config_file)#todo remove commentout
    fill_in_config_template(run_id, deployment_project, test_project, pubsub_test_token)
    _ = run_command(f"./deploy.sh {deployment_project}")  # can fail
    atexit.register(
        lambda: clean_resources(run_id, deployment_project, test_project, gce_zone)
    )
    wait_for_deployment(deployment_project)
    create_resources(run_id, test_project, gce_zone)
    describe_resources(run_id, test_project, gce_zone)
    end = time.time()
    print("Elapsed time", int(end - start_test))


def gce_region(gce_zone):
    return gce_zone[: gce_zone.rfind("-")]


def wait_for_deployment(deployment_project):
    start_deploy = time.time()
    from util.deployment_time import (
        deployment_time,
    )  # Import only now, after modification

    this_version_deploy_time = datetime.datetime.fromtimestamp(deployment_time)
    url = f"https://iris3-dot-{deployment_project}.uc.r.appspot.com/"
    while time.time() - start_deploy < 180:  # break after 180 sec
        with urllib.request.urlopen(url) as response:
            txt_b = response.read()
            txt = str(txt_b, "UTF-8")
            results = re.findall(r"Deployed (\S*)", txt)
            assert len(results) == 1
            on_site = datetime.datetime.fromisoformat(results[0])
            if on_site == this_version_deploy_time:
                return
    raise TimeoutError(time.time() - start_deploy)


def fill_in_config_template(
    run_id, deployment_project, test_project, pubsub_test_token
):
    with open("config.yaml.test.template") as template_file:
        filled_template = template_file.read()
        local_variables = locals().copy()
        for name, val in local_variables.items():
            filled_template = filled_template.replace("${" + name.upper() + "}", str(val))
        print(os.path.abspath(config_test_yaml))
    assert "${" not in filled_template, filled_template
    with open(config_test_yaml, "w") as config_test:
        config_test.write(filled_template)



# Revert config on exit
def remove_config_file():
    try:
        os.remove(config_test_yaml)
    except FileNotFoundError:
        pass  # OK


def clean_resources(run_id, deployment_project, test_project, gce_zone):

    remove_config_file()
    commands = [
        f"gcloud compute instances delete instance{run_id} -q --project {test_project}  --zone {gce_zone}",
        f"gcloud compute snapshots delete snapshot{run_id} -q --project {test_project}",
        f"gcloud compute disks delete disk{run_id} -q --project {test_project} --zone {gce_zone}",
        f"gcloud pubsub topics delete topic{run_id} -q --project {test_project}",
        f"gcloud pubsub subscriptions delete subscription{run_id} -q --project {test_project}",
        f"bq rm -f --table {test_project}:dataset{run_id}.table{run_id}",
        f"bq rm -f --dataset {test_project}:dataset{run_id}",
        f"gsutil rm -r gs://bucket{run_id}",
        f"gcloud app services delete iris3 -q --project {deployment_project}",
    ]
    with ThreadPoolExecutor() as executor:
        failed = [
            cmd
            for cmd, result in zip(
                commands, executor.map(run_command_or_commands_catch_exc, commands)
            )
            if isinstance(result, Exception)
        ]
    if failed:
        print("Failed to delete", failed)
        set_failing(True)
        sys.exit(1)

    return 1 if failing else 0


def check_enough_command_line_params():
    if len(sys.argv) < 3:
        print(
            """
       Usage: integration_test.py deployment-project project-under-test [execution-id]
          - The project to which Iris is deployed
          - The project where resources will be labeled (can be the same project)
          - An optional lower-case alphanumerical string to identify this run,
               used as a prefix on Iris labels and as part of the name of launched resources.
               If omitted, one will be generated.
          Returns exit code 0 on test-success, non-zero on test-failure
      """
        )
        set_failing(True)
        sys.exit(1)


def get_run_id():
    if len(sys.argv) > 3:
        run_id = sys.argv[3]
    else:
        # Random value to distinguish this test runs from others
        run_id = random_str(4)
    return run_id


def check_legal_run_id(run_id):
    if any(x in run_id for x in "_-"):
        print(
            """
            Illegal run id $RUN_ID. No dashes or underlines permitted because
            underlines are illegal in snapshot (and other) names
            and dashes are illegal in BigQuery names.
            """
        )
        set_failing(True)
        sys.exit(1)


def check_projects_exist(deployment_project, test_project):
    projects = [deployment_project, test_project]

    def check_project_exists(proj):
        try:
            return run_command(f"gcloud projects describe {proj}")
        except CalledProcessError:
            return None

    with ThreadPoolExecutor() as executor:
        failed = [
            p
            for p, result in zip(projects, executor.map(check_project_exists, projects))
            if not result
        ]

    if failed:
        raise Exception("Illegal project(s)", ",".join(failed))




def create_resources(run_id, test_project, gce_zone):
    commands = [  # Some must be run sequentially
        [
            f"gcloud compute instances create instance{run_id} --project {test_project} --zone {gce_zone}",
            f"gcloud compute disks create disk{run_id} --project {test_project} --zone {gce_zone}",
            f"gcloud compute snapshots create snapshot{run_id} --source-disk instance{run_id} --source-disk-zone {gce_zone} --storage-location  {gce_region(gce_zone)} --project {test_project}",
        ],
        [
            f"gcloud pubsub topics create topic{run_id} --project {test_project}",
            f"gcloud pubsub subscriptions create subscription{run_id} --topic topic{run_id} --project {test_project}",
        ],
        [
            f"bq mk --dataset test_project:dataset{run_id}",
            f"bq mk --table {test_project}:dataset{run_id}.table{run_id}",
        ],
        f"gsutil mb -p {test_project} gs://bucket{run_id}",
    ]

    with ThreadPoolExecutor() as executor:
        failed = [
            cmd
            for cmd, result in zip(
                commands, executor.map(run_command_or_commands_catch_exc, commands)
            )
            if isinstance(result, Exception)
        ]
    if failed:
        print("Failed ", failed)
        set_failing(True)
        sys.exit(1)



if __name__ == "__main__":
    main()