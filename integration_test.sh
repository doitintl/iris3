#!/bin/bash

# This is an integration test with a deployed app and deployed cloud resources.
# * Deploys to the cloud with a unique run-id
# * Creates resources of all supported types except Cloud SQL
# * Checks that a label was added to each resource,
# * Deletes the resources.
#
# See usage text for parameters.

set -u
set -e
set -x

START_TEST=$(date "+%s")

if [[ $# -lt 2 ]]; then

  cat >&2 <<EOF
 Usage: integration_test.sh deployment-project project-under-test [execution-id]
    - The project to which Iris is deployed
    - The project where resources will be labeled (can be the same project)
    - An optional lower-case alphanumerical string to identify this run,
         used as a prefix on Iris labels and as part of the name of launched resources.
         If omitted, one will be generated.
    Returns exit code 0 on test-success, non-zero on test-failure
EOF
  exit
fi

export RUN_ID
if [[ $# -eq 3 ]]; then
  RUN_ID=$3
else
  # Random value to distinguish this test runs from others
  RUN_ID="iris$(base64 </dev/urandom | tr -d '+/' | head -c 6 | awk '{print tolower($0)}')"
fi

export DEPLOYMENT_PROJECT=$1
export TEST_PROJECT=$2
declare -a projects
projects=("$DEPLOYMENT_PROJECT" "$TEST_PROJECT")
for p in "${projects[@]}"; do
  gcloud projects describe "$p" || {
    echo >&2 "Project $p not found"
    exit 1
  }
done

gcloud config set project "$TEST_PROJECT"

if [ -n "$(echo "$RUN_ID" | grep '[_-]')" ]; then

  cat >&2 <<EOF
     Illegal run id $RUN_ID. No dashes or underlines permitted because
    underlines are illegal in snapshot (and other) names
    and dashes are illegal in BigQuery names.
EOF
  exit 1
fi

# Set up the config file for the deployment
mv config.yaml config.yaml.original

# Prepare to revert that on exit
function revert_config() {
  # Cleanup should not stop on error
  set +e
  echo >&2 "Reverting"
  mv config.yaml.original config.yaml
}

trap "revert_config" EXIT

envsubst <config.yaml.test.template >config.yaml

./deploy.sh $DEPLOYMENT_PROJECT

# Cleanup on exit
function clean_resources() {
  EXIT_CODE=$?
  # Cleanup should not stop on error
  set +e
  # Include the earlier on-exit code inside this one.
  revert_config

  gcloud compute instances delete "instance${RUN_ID}" -q --project "$TEST_PROJECT"
  gcloud compute snapshots delete "snapshot${RUN_ID}" -q --project "$TEST_PROJECT"
  gcloud compute disks delete "disk${RUN_ID}" -q --project "$TEST_PROJECT"
  gcloud pubsub topics delete "topic${RUN_ID}" -q --project "$TEST_PROJECT"
  gcloud pubsub subscriptions delete "subscription${RUN_ID}" -q --project "$TEST_PROJECT"
  gcloud bigtable instances delete "bigtable${RUN_ID}" -q --project "$TEST_PROJECT"
  bq rm -f --table "${TEST_PROJECT}:dataset${RUN_ID}.table${RUN_ID}"
  bq rm -f --dataset "${TEST_PROJECT}:dataset${RUN_ID}"
  gsutil rm -r "gs://bucket${RUN_ID}"
  gcloud app services delete -q iris3 --project $DEPLOYMENT_PROJECT

  FINISH_TEST=$(date "+%s")
  ELAPSED_SEC_TEST=$((FINISH_TEST - START_TEST))
  echo >&2 "Elapsed time for $(basename "$0") ${ELAPSED_SEC_TEST} s; exiting with $EXIT_CODE"

  exit $EXIT_CODE
}
trap "clean_resources" EXIT

sleep 20 # Need time for traffic to be migrated to the new version

gcloud compute instances create "instance${RUN_ID}" --project "$TEST_PROJECT"
gcloud compute disks create "disk${RUN_ID}" --project "$TEST_PROJECT"
gcloud compute disks snapshot "instance${RUN_ID}" --snapshot-names "snapshot${RUN_ID}" --project $TEST_PROJECT
gcloud pubsub topics create "topic${RUN_ID}" --project "$TEST_PROJECT"
gcloud pubsub subscriptions create "subscription${RUN_ID}" --topic "topic${RUN_ID}" --project "$TEST_PROJECT"
gcloud bigtable instances create "bigtable${RUN_ID}" --display-name="bigtable${RUN_ID}" --cluster="bigtable${RUN_ID}" --cluster-zone=us-east1-c --project "$TEST_PROJECT"
bq mk --dataset "${TEST_PROJECT}:dataset${RUN_ID}"
bq mk --table "${TEST_PROJECT}:dataset${RUN_ID}.table${RUN_ID}"
gsutil mb -p $TEST_PROJECT "gs://bucket${RUN_ID}"

# It takes about time seconds before  labels are available to be read by "describe".
#
# jq -e generates exit code 1 on failure. Since we set -e, the script will fail appropriately if the value is not found

sleep 20

DESCRIBE_FLAGS=(--project "$TEST_PROJECT" --format json)
JQ=(jq -e ".labels.${RUN_ID}_name")

gcloud compute instances describe "instance${RUN_ID}" "${DESCRIBE_FLAGS[@]}" | "${JQ[@]}"
gcloud compute disks describe "disk${RUN_ID}" "${DESCRIBE_FLAGS[@]}" | "${JQ[@]}"
gcloud compute snapshots describe "snapshot${RUN_ID}" "${DESCRIBE_FLAGS[@]}" | "${JQ[@]}"
gcloud pubsub topics describe "topic${RUN_ID}" "${DESCRIBE_FLAGS[@]}" | "${JQ[@]}"
gcloud pubsub subscriptions describe "subscription${RUN_ID}" "${DESCRIBE_FLAGS[@]}" | "${JQ[@]}"
gcloud bigtable instances describe "bigtable${RUN_ID}" "${DESCRIBE_FLAGS[@]}" | "${JQ[@]}"
bq show --format=json "${TEST_PROJECT}:dataset${RUN_ID}" | "${JQ[@]}"
bq show --format=json "${TEST_PROJECT}:dataset${RUN_ID}.table${RUN_ID}" | "${JQ[@]}"
# For buckets, JSON shows labels without the label:{} wrapper seen in  the others
gsutil label get "gs://bucket${RUN_ID}" | jq -e ".${RUN_ID}_name"

#clean up and exit in clean_resources, which is called on exit
