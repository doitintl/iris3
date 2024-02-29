import atexit
import datetime
import json
import logging
import os
import random
import re
import sys
import time
import urllib.request
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from subprocess import CalledProcessError
from typing import Union, List
from urllib.error import HTTPError

from util.config_utils import iris_prefix, iris_homepage_text
from util.utils import (
    random_str,
    random_hex_str,
    run_command,
    log_time,
    set_log_levels,
)


class BaseIntegTest(ABC):
    config_test_yaml = "config-test.yaml"

    GCE_ZONE = "europe-central2-b"

    def __init__(self):
        self.__test_start = str(datetime.datetime.now())[:-7]
        print("Starting test at", self.__test_start, "local time")

        self.exit_code = 0

    def deploy_test_and_uninstall(self):
        start_test = time.time()
        set_log_levels()
        (
            deployment_project,
            test_project,
            run_id,
            gce_zone,
        ) = self.__configuration()
        self.__deploy(deployment_project)

        self.__create_check_and_delete_resources(test_project, gce_zone, run_id)

        self.__uninstall(deployment_project)
        end = time.time()
        print("Time for integration test", int(end - start_test), "s")

    @log_time
    def __describe_resources(self, test_project, run_id, gce_zone) -> Union[List, bool]:
        commands = self._resource_description_commands(gce_zone, run_id, test_project)
        assert all(isinstance(x, str) for x in commands), commands
        with ThreadPoolExecutor(10) as executor:
            commands_and_executors = list(
                zip(
                    commands,
                    executor.map(self.__run_command_or_commands_catch_exc, commands),
                )
            )
            failed_in_getting_any_string_back = [
                cmd
                for cmd, result in commands_and_executors
                if isinstance(result, Exception)
            ]
            got_some_string_back = [
                (cmd, result)
                for cmd, result in commands_and_executors
                if not isinstance(result, Exception)
            ]

        if failed_in_getting_any_string_back:
            print(
                "Failed to get any description:",
                failed_in_getting_any_string_back,
                "\nGot some description back:",
                got_some_string_back,
            )
            return False
        else:
            needed_label_not_found = []
            needed_label_found = []
            for cmd, cmd_output in got_some_string_back:
                if "gsutil" in cmd:
                    extraction_method = self.__extract_labels_from_result_for_gsutil
                else:
                    extraction_method = self.__extract_labels_from_result_non_gcs

                extraction_method(
                    cmd, cmd_output, run_id, needed_label_found, needed_label_not_found
                )

            if len(needed_label_not_found) > 0:
                print(
                    len(needed_label_found),
                    "labels found;",
                    'Needed labels not found: "'
                    + "; ".join(
                        self.__short_version_of_commands(needed_label_not_found)
                    )
                    + '"',
                )

            return needed_label_not_found

    @staticmethod
    def __extract_labels_from_result_for_gsutil(
        cmd, cmd_output, run_id, needed_label_found, needed_label_not_found
    ):
        try:
            j = json.loads(cmd_output)
            # GCS is different in two ways
            # 1. Because we are using a label-specific command  "gsutils labels", there is "No "labels" wrapper in the JSON
            # 2. For the sake of a  testing resource-type specific labels, bucket labels start "gcs", not the usual iris prefix.
            label_val = j.get(f"gcs{run_id}_name")

        except json.decoder.JSONDecodeError as e:
            logging.exception("")
            print("Exception", e, 'for output"', cmd_output, '"')
            label_val = None

        if label_val:
            needed_label_found.append(cmd)
        else:
            needed_label_not_found.append(cmd)

    @staticmethod
    def __extract_labels_from_result_non_gcs(
        cmd, cmd_output, run_id, needed_label_found, needed_label_not_found
    ):
        j = json.loads(cmd_output)
        labels = j.get("labels", {})
        label_val = labels.get(f"{run_id}_name")
        if label_val:
            needed_label_found.append(cmd)
        else:
            needed_label_not_found.append(cmd)

    @log_time
    def __create_resources(self, test_project, run_id, gce_zone):
        commands = self._resource_creation_commands(gce_zone, run_id, test_project)

        with ThreadPoolExecutor(10) as executor:
            creation_failed = [
                cmd
                for cmd, result in zip(
                    commands,
                    executor.map(self.__run_command_or_commands_catch_exc, commands),
                )
                if isinstance(result, Exception)
            ]
        if creation_failed:
            print("Failed ", creation_failed)
            self.__set_failing()

    @log_time
    def __delete_resources(self, resources_project, run_id, gce_zone):
        # pause_for_user_input()# Use this in debugging, to keep the test resources alive until you hit E

        self.remove_temporary_test_config_file()
        commands = self._resource_deletion_commands(gce_zone, resources_project, run_id)
        with ThreadPoolExecutor() as executor:
            failed = [
                cmd
                for cmd, result in zip(
                    commands,
                    executor.map(self.__run_command_or_commands_catch_exc, commands),
                )
                if isinstance(result, Exception)
            ]
        if failed:
            print("Failed to delete", failed)

    def __set_failing(self):
        self.exit_code = 1

    @staticmethod
    def __run_cmd_catch_exc(cmd):
        try:
            return run_command(cmd)
        except CalledProcessError as e:
            logging.exception(f"Calling {cmd}")
            return e

    @classmethod
    def __run_command_or_commands_catch_exc(
        cls, command_or_commands: Union[str, List[str]]
    ):
        time.sleep(random.randint(0, 3))  # Avoid thundering herd
        if isinstance(command_or_commands, str):
            command = command_or_commands
            return cls.__run_cmd_catch_exc(command)
        else:
            ret = []
            for i in range(len(command_or_commands)):
                one_return_value = cls.__run_cmd_catch_exc(command_or_commands[i])
                if isinstance(one_return_value, Exception):
                    return (
                        one_return_value  # Return only the exception on first failure
                    )
                else:
                    ret.append(one_return_value)
                # The second sequential command sometimes prevents the
                # *first* from working. So, CreateTopic never generates a request to label_one.
                # Maybe CreateInstance also, though more rarely.
                # I don't know why.
                if i < len(command_or_commands) - 1:
                    time.sleep(random.randint(5, 10))

            return ret

    @classmethod
    def __get_gcs_label(cls, run_id, result: Union[str, Exception]):
        cmd = ""
        label_val = None
        if isinstance(result, Exception):
            print("Failed to describe bucket:", cmd)
        else:
            assert isinstance(result, str), type(result)
            if result.strip() == "":
                label_val = ""
            else:
                try:
                    j = json.loads(result)
                    # In GCS, no "labels" wrapper for the actual label
                    # Also, for a test of labels that are specific to a resource type,
                    # bucket labels start "gcs"
                    label_val = j.get(f"gcs{run_id}_name")
                except json.decoder.JSONDecodeError as e:
                    print(e, 'for output"', result, '"')
                    label_val = None

            if not label_val:
                print("GCS bucket did not have the needed label")
        return result, label_val

    @staticmethod
    @log_time
    def __uninstall(deployment_project):

        _ = run_command(
            # Just uninstall the proj-level elements because uninstalling the org leaves us with a "soft-deleted" role
            #   f"./uninstall.sh -p {deployment_project}",
            # Just uninstall the App Engine because there is a strict quota/limit on iam-binding
            f"gcloud app services delete --project {deployment_project} -q iris3"
        )

    def __create_check_and_delete_resources(self, iris_project, gce_zone, run_id):
        try:
            succeed = self.__create_and_describe_resources(
                iris_project, run_id, gce_zone
            )
            if not succeed:
                self.__set_failing()
        except:
            logging.exception("")

        self.__delete_resources(iris_project, run_id, gce_zone)

    @classmethod
    @log_time
    def __deploy(cls, deployment_project):
        _ = run_command(
            f"./deploy.sh {deployment_project}",
            extra_env={"SKIP_ADDING_IAM_BINDINGS": "true"},
        )  # can fail
        cls.wait_for_traffic_shift(deployment_project)

    @log_time
    def __configuration(self):
        self.check_usage()
        deployment_project = sys.argv[1]
        test_project = sys.argv[2]

        run_id = self.generate_run_id()

        # pubsub_test_token is used for envsubst into config.yaml.test.template
        pubsub_test_token = random_hex_str(20)

        self.check_projects_exist(deployment_project, test_project)
        _ = run_command(f"gcloud config set project {test_project}")
        self.remove_temporary_test_config_file()
        atexit.register(self.remove_temporary_test_config_file)
        self.fill_in_config_template(
            run_id, deployment_project, test_project, pubsub_test_token
        )
        return deployment_project, test_project, run_id, self.GCE_ZONE

    @staticmethod
    def __short_version_of_commands(commands: List[str]) -> List[str]:
        ret = []
        for c in commands:
            words = c.split()

            if words[0] == "bq":
                ret.append(" ".join(words[0:2]))
            else:
                assert words[0] == "gcloud", words
                ret.append(" ".join(words[1:3]))
        return ret

    def __create_and_describe_resources(self, test_project, run_id, gce_zone) -> bool:
        self.__create_resources(test_project, run_id, gce_zone)

        start = time.time()
        try_count = 0
        labels_not_found = []
        try:
            while time.time() - start < 120:  # Go at most 2 minutes
                try_count += 1
                # Could loop for each command separately. As-is, we "wastefully" recheck
                # all resources so long as just one is missing a label.
                labels_not_found: Union[List, bool] = self.__describe_resources(
                    test_project, run_id, gce_zone
                )

                if labels_not_found is False:
                    print("Exceptions in getting descriptions")
                    return False
                elif len(labels_not_found) == 0:
                    print("Succeeded finding all labels")
                    return True  # Sucess: break if we found all relevant labels
                else:
                    print("Still looking for", len(labels_not_found), "labels")

                    print(
                        "Label-check loop #",
                        try_count,
                        int(time.time() - start),
                        "seconds;",
                        len(labels_not_found),
                        "labels found so far;",
                        'Needed labels not found yet: "'
                        + "; ".join(self.__short_version_of_commands(labels_not_found))
                        + '"',
                    )
                    time.sleep(2)  # Try again

            assert len(labels_not_found) > 0, "only get here on failure"
            print(
                "Exiting with failure;",
                len(labels_not_found),
                "needed labels not found:\n\t\t",
                "\n\t\t".join(labels_not_found),
            )

            # wait_for_user_input()

            return False
        finally:
            self.__write_results(labels_not_found)

            print(
                "Exiting checks of labels after",
                try_count,
                "loops;",
                int(time.time() - start),
                "seconds",
            )

    def __write_results(self, labels_not_found):
        try:
            os.mkdir("./testresults")
        except:
            pass

        with open("./testresults/failurecount.csv", "a") as fa:
            fa.write(f"{len(labels_not_found)}\n"),

        with open(
            f"./testresults/testresult-{self.__test_start.replace(':', '').replace(' ', 'T')}.txt",
            "w",
        ) as f:
            f.write("Start time: " + self.__test_start + "\n")
            f.write("Iris prefix: " + iris_prefix() + "\n")
            f.write("Success: " + str(not bool(labels_not_found)) + "\n")
            f.write(
                f"Count of resources for which label was not found: {len(labels_not_found)}\n"
            ),
            f.write("\t" + "\n\t".join(labels_not_found))

    @classmethod
    def wait_for_traffic_shift(cls, deployment_project):
        start_wait_for_trafficshift = time.time()
        url = cls.gae_url_with_multiregion_abbrev(deployment_project)
        while time.time() - start_wait_for_trafficshift < 180:  # break after 180 sec
            try:
                found_it = cls.__check_for_new_v(start_wait_for_trafficshift, url)
                if found_it:
                    return
                else:
                    time.sleep(1)
                    continue
            except HTTPError as e:
                logging.error(e)  # Keep trying despite exception

        raise TimeoutError(time.time() - start_wait_for_trafficshift)

    @classmethod
    def gae_url_with_multiregion_abbrev(cls, proj):
        """return: Something like
        https://iris3-dot-<PROJECTID>.<MULTIREGION_ABBREV>.r.appspot.com/
        Where MULTIREGION_ABBREV may be uc (us-central), sa (southeast-asia)m or others.

        In script _deploy.project.sh, similar functionality appears (as Bash)
        """
        app_describe = cls.__run_cmd_catch_exc(f"gcloud app describe --project {proj}")
        search = re.search(r"defaultHostname: (.*)$", app_describe, re.MULTILINE)
        url_base = search.group(1)
        assert "https://" not in url_base and "iris3-dot-" not in url_base, url_base
        return "https://" + "iris3-dot-" + url_base

    @staticmethod
    def __check_for_new_v(start_wait_for_trafficshift, url) -> bool:
        with urllib.request.urlopen(url) as response:
            txt_b = response.read()
            txt = str(txt_b, "UTF-8")
            time_waiting = round((time.time() - start_wait_for_trafficshift), 1)
            if iris_homepage_text() in txt:
                print(
                    "Wait for traffic shift took",
                    time_waiting,
                    "sec",
                )
                return True
            print(
                'Site now returns "',
                txt[:100],
                '...", which does not yet include the expected iris_prefix',
                iris_prefix(),
                "\nSo far waited",
                time_waiting,
                "sec",
            )
            return False

    @classmethod
    def fill_in_config_template(
        cls, run_id, deployment_project, test_project, pubsub_test_token
    ):
        with open("config.yaml.test.template") as template_file:
            filled_template = template_file.read()
            local_variables = locals().copy()
            for name, val in local_variables.items():
                filled_template = filled_template.replace(
                    "${" + name.upper() + "}", str(val)
                )

        assert "${" not in filled_template, filled_template
        with open(cls.config_test_yaml, "w") as config_test:
            config_test.write(filled_template)

    # Revert config on exit
    @classmethod
    def remove_temporary_test_config_file(cls):
        try:
            os.remove(cls.config_test_yaml)
        except FileNotFoundError:
            pass  # OK

    def check_usage(self):
        if len(sys.argv) < 3:
            print(
                """
           Usage: integration_test.py iris-project resource-project  [execution-id]
              - iris-project: The project to which Iris is deployed
              - resource-project: The project where resources will be created and labeled (can be the same project)
              - An optional lower-case alphanumerical string to identify this run,
                   used as a prefix on Iris labels and as part of the name of launched resources.
                   If omitted, one will be generated.
              Returns exit code 0 on test-success, non-zero on test-failure
          """
            )
            self.__set_failing()
            sys.exit(1)

    @staticmethod
    def generate_run_id():
        # Random value to distinguish this test runs from others
        run_id = random_str(4)
        print("run_id is", run_id, file=sys.stderr)
        return run_id

    @staticmethod
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
                for p, result in zip(
                    projects, executor.map(check_project_exists, projects)
                )
                if not result
            ]

        if failed:
            raise Exception("Illegal project(s)", ",".join(failed))

    @abstractmethod
    def _resource_deletion_commands(
        self, gce_zone, resources_project, run_id
    ) -> List[Union[List[str], str]]:

        pass

    @abstractmethod
    def _resource_creation_commands(
        self, gce_zone, run_id, test_project
    ) -> List[Union[List[str], str]]:
        pass

    @abstractmethod
    def _resource_description_commands(
        self, gce_zone, run_id, test_project
    ) -> List[str]:
        pass
