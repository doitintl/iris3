import atexit
import json
import logging
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from subprocess import CalledProcessError
from typing import Union, List
from urllib.error import HTTPError

from test_scripts.utils_for_tests import assert_root_path
from util.config_utils import iris_prefix, iris_homepage_text
from util.utils import (
    random_str,
    random_hex_str,
    run_command,
    log_time,
    set_log_levels,
)

config_test_yaml = "config-test.yaml"

GCE_ZONE = "europe-central2-b"

exit_code = 0


def set_failing():
    global exit_code
    exit_code = 1


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


@log_time
def describe_resources(test_project, run_id, gce_zone):
    describe_flags = f"--project {test_project} --format json"
    commands = [
        f"gcloud pubsub topics describe topic{run_id} {describe_flags}",
        f"gcloud pubsub subscriptions describe subscription{run_id} {describe_flags}",
        f"bq show --format=json {test_project}:dataset{run_id}",
        f"bq show --format=json {test_project}:dataset{run_id}.table{run_id}",
        f"gcloud compute instances describe instance{run_id} --zone {gce_zone} {describe_flags}",
        f"gcloud compute disks describe disk{run_id} --zone {gce_zone} {describe_flags}",
        f"gcloud compute snapshots describe snapshot{run_id} {describe_flags}",
    ]
    with ThreadPoolExecutor(10) as executor:
        commands_and_executors = list(
            zip(commands, executor.map(run_command_or_commands_catch_exc, commands))
        )
        did_not_get_descrip = [cmd for cmd, result in commands_and_executors if isinstance(result, Exception)]
        got_a_description = {
            cmd: result for cmd, result in commands_and_executors if not isinstance(result, Exception)
        }
    if did_not_get_descrip:
        print("Failed to get any desc", did_not_get_descrip, "\nGot some desc", got_a_description)
        set_failing()
    else:
        needed_label_not_found = []
        found=[]
        for cmd, result in got_a_description.items():
            j = json.loads(result)
            label = j["labels"]
            label_val = label.get(f"{run_id}_name")
            if   label_val:
                needed_label=found.append(cmd)
            else:
                needed_label_not_found.append(cmd)

        if needed_label_not_found:
            print("Needed label not found", needed_label_not_found,
                  "\nNeeded label found",found)
            set_failing()

    gcs_cmd = f"gsutil label get gs://bucket{run_id}"
    out = run_command_or_commands_catch_exc(gcs_cmd)
    if isinstance(out, Exception):
        print("Failed to describe bucket:", gcs_cmd)
        set_failing()
    else:
        assert isinstance(out, str), type(out)
        j = json.loads(out)
        # In GCS, no "labels" wrapper for the actual label
        # Also, for a test of labels that are specific to a resource type,
        # bucket labels start "gcs"
        label_val = j.get(f"gcs{run_id}_name")
        if not label_val:
            print("GCS did not have the needed label")
            set_failing()
    if not exit_code:
      print("Success: All needed labels found")


def main():
    start_test = time.time()
    set_log_levels()
    deployment_project, test_project, run_id, gce_zone = setup_configuration()
    deploy(deployment_project)

    try:
        create_and_describe_resources(test_project, run_id, gce_zone)
    except Exception:
        logging.exception("")

    clean_resources(deployment_project, test_project, run_id, gce_zone)
    end = time.time()
    print("Time for integration test", int(end - start_test), "s")


@log_time
def deploy(deployment_project):
    _ = run_command(f"./deploy.sh {deployment_project}")  # can fail
    wait_for_traffic_shift(deployment_project)


@log_time
def setup_configuration():
    count_command_line_params()
    deployment_project = sys.argv[1]
    test_project = sys.argv[2]
    run_id = get_run_id()

    # pubsub_test_token is used for envsubst into config.yaml.test.template
    pubsub_test_token = random_hex_str(20)
    gce_zone = GCE_ZONE
    check_projects_exist(deployment_project, test_project)
    _ = run_command(f"gcloud config set project {test_project}")
    remove_config_file()
    atexit.register(remove_config_file)
    fill_in_config_template(run_id, deployment_project, test_project, pubsub_test_token)
    return (
        deployment_project,
        test_project,
        run_id,
        gce_zone,
    )


def create_and_describe_resources(test_project, run_id, gce_zone):
    create_resources(test_project, run_id, gce_zone)
    describe_resources(test_project, run_id, gce_zone)


def gce_region(gce_zone):
    return gce_zone[: gce_zone.rfind("-")]


def wait_for_traffic_shift(deployment_project):
    start_wait_for_trafficshift = time.time()

    url = f"https://iris3-dot-{deployment_project}.uc.r.appspot.com/"
    while time.time() - start_wait_for_trafficshift < 180:  # break after 180 sec
        try:
            found_it = __check_for_new_v(start_wait_for_trafficshift, url)
            if found_it:
                return
            else:
                time.sleep(3)
                continue
        except HTTPError as e:
            logging.error(e)  # Keep trying despite exception

    raise TimeoutError(time.time() - start_wait_for_trafficshift)


def __check_for_new_v(start_wait_for_trafficshift, url) -> bool:
    with urllib.request.urlopen(url) as response:
        txt_b = response.read()
        txt = str(txt_b, "UTF-8")
        if iris_homepage_text() in txt:
            print(
                "Wait for traffic shift took",
                int(1000 * (time.time() - start_wait_for_trafficshift)),
                "msec",
            )
            return True
        print(
            'Site now has "',
            txt[:100],
            '"not including the expected ',
            iris_prefix(),
        )
        return False


def fill_in_config_template(
    run_id, deployment_project, test_project, pubsub_test_token
):
    with open("config.yaml.test.template") as template_file:
        filled_template = template_file.read()
        local_variables = locals().copy()
        for name, val in local_variables.items():
            filled_template = filled_template.replace(
                "${" + name.upper() + "}", str(val)
            )

    assert "${" not in filled_template, filled_template
    with open(config_test_yaml, "w") as config_test:
        config_test.write(filled_template)


# Revert config on exit
def remove_config_file():
    try:
        os.remove(config_test_yaml)
    except FileNotFoundError:
        pass  # OK


@log_time
def clean_resources(deployment_project, test_project, run_id, gce_zone):
    remove_config_file()
    commands = [
        f"gcloud compute instances delete -q instance{run_id} --project {test_project} --zone {gce_zone}",
        f"gcloud compute snapshots delete -q snapshot{run_id} --project {test_project}",
        f"gcloud compute disks delete -q disk{run_id} --project {test_project} --zone {gce_zone}",
        f"gcloud pubsub topics delete -q topic{run_id} --project {test_project}",
        f"gcloud pubsub subscriptions -q delete subscription{run_id} --project {test_project}",
        [
            f"bq rm -f --table {test_project}:dataset{run_id}.table{run_id}",
            f"bq rm -f --dataset {test_project}:dataset{run_id}",
        ],
        f"gsutil rm -r gs://bucket{run_id}",
        f"gcloud app services delete -q iris3 --project {deployment_project}",
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
    # Do not set_failing. If we fail on cleanup,there is not much to do


def count_command_line_params():
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
        set_failing()
        sys.exit(1)


def get_run_id():
    if len(sys.argv) > 3:
        run_id = sys.argv[3]
    else:
        # Random value to distinguish this test runs from others
        run_id = random_str(4)
    print("run_id is", run_id, file=sys.stderr)
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
        set_failing()
        sys.exit(1)


def check_projects_exist(deployment_project, test_project):
    projects = [deployment_project, test_project]

    def check_project_exists(proj):
        try:
            return run_command(f"gcloud projects describe {proj}")
        except CalledProcessError:
            return None

    with ThreadPoolExecutor(10) as executor:
        failed = [
            p
            for p, result in zip(projects, executor.map(check_project_exists, projects))
            if not result
        ]

    if failed:
        raise Exception("Illegal project(s)", ",".join(failed))


@log_time
def create_resources(test_project, run_id, gce_zone):
    commands = [  # Some must be run sequentially
        f"gcloud compute instances create instance{run_id} --project {test_project} --zone {gce_zone}",
        [
            f"gcloud compute disks create disk{run_id} --project {test_project} --zone {gce_zone}",
            f"gcloud compute snapshots create snapshot{run_id} --source-disk disk{run_id} --source-disk-zone {gce_zone} --storage-location {gce_region(gce_zone)} --project {test_project}",
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

    with ThreadPoolExecutor(10) as executor:
        failed = [
            cmd
            for cmd, result in zip(
                commands, executor.map(run_command_or_commands_catch_exc, commands)
            )
            if isinstance(result, Exception)
        ]
    if failed:
        print("Failed ", failed)
        set_failing()


if __name__ == "__main__":
    assert_root_path()

    main()
    print("Exiting with", "failure" if exit_code else "success")
    sys.exit(exit_code)
