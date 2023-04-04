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

# RUN_ID envsubst into config.yaml.test.template
export RUN_ID
if [[ $# -eq 3 ]]; then
  RUN_ID=$3
else
  # Random value to distinguish this test runs from others
  RUN_ID="iris$(base64 </dev/urandom | tr -d '+/' | head -c 6 | awk '{print tolower($0)}')"
fi


export PUBSUB_TEST_TOKEN
# PUBSUB_TEST_TOKEN is used for envsubst into config.yaml.test.template
PUBSUB_TEST_TOKEN=$(hexdump -n 16 -e '4/4 "%08X" 1 "\n"' /dev/urandom| tr '[:upper:]' '[:lower:]')
# DEPLOYMENT_PROJECT and TEST_PROJECT is used for envsubst into config.yaml.test.template
export DEPLOYMENT_PROJECT=$1
export TEST_PROJECT=$2


GCE_ZONE=europe-central2-b
GCE_REGION=$(echo $GCE_ZONE |egrep -o "[a-z0-9]+-[a-z0-9]+-"|  rev | cut -c2- | rev)


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

rm config-test.yaml ||true

# Prepare to revert config on exit
function revert_config() {
  # Cleanup should not stop on error
  set +e
  echo >&2 "Reverting config"
  rm config-test.yaml ||true
}

trap "revert_config" EXIT

envsubst <config.yaml.test.template > config-test.yaml

# GAEVERSION is exported to deploy.sh
export GAEVERSION=$RUN_ID

./deploy.sh $DEPLOYMENT_PROJECT

ERROR=0

# Cleanup on exit
function clean_resources() {
  STATUS_BEFORE_TRAPEXIT=$?
  if  (("$ERROR" == 0 )) ; then
    EXIT_CODE=$STATUS_BEFORE_TRAPEXIT
  else
    EXIT_CODE="$ERROR"
  fi

  echo >&2 "Cleaning up resources. Exit code will be $STATUS_BEFORE_TRAPEXIT; Stored code was $ERROR; Status code was $STATUS_BEFORE_TRAPEXIT"

  # Cleanup should not stop on error
  set +e

  # Include the earlier on-exit code inside this one.
  revert_config

  gcloud compute instances delete "instance${RUN_ID}" -q --project "$TEST_PROJECT"  --zone $GCE_ZONE
  gcloud compute snapshots delete "snapshot${RUN_ID}" -q --project "$TEST_PROJECT"
  gcloud compute disks delete "disk${RUN_ID}" -q --project "$TEST_PROJECT" --zone $GCE_ZONE
  gcloud pubsub topics delete "topic${RUN_ID}" -q --project "$TEST_PROJECT"
  gcloud pubsub subscriptions delete "subscription${RUN_ID}" -q --project "$TEST_PROJECT"
  bq rm -f --table "${TEST_PROJECT}:dataset${RUN_ID}.table${RUN_ID}"
  bq rm -f --dataset "${TEST_PROJECT}:dataset${RUN_ID}"
  gsutil rm -r "gs://bucket${RUN_ID}"

  gcloud app services delete iris3 -q --project $DEPLOYMENT_PROJECT

  FINISH_TEST=$(date "+%s")
  ELAPSED_SEC_TEST=$((FINISH_TEST - START_TEST))
  echo >&2 "Elapsed time for $(basename "$0") ${ELAPSED_SEC_TEST} s; exiting with $ERROR"

  exit $EXIT_CODE
}
trap "clean_resources" EXIT

sleep 30 # Need time for traffic to be migrated to the new version

gcloud compute instances create "instance${RUN_ID}" --project "$TEST_PROJECT" --zone $GCE_ZONE
gcloud compute disks create "disk${RUN_ID}" --project "$TEST_PROJECT" --zone $GCE_ZONE
gcloud compute snapshots create "snapshot${RUN_ID}" --source-disk "instance${RUN_ID}" --source-disk-zone $GCE_ZONE --storage-location $GCE_REGION --project $TEST_PROJECT
gcloud pubsub topics create "topic${RUN_ID}" --project "$TEST_PROJECT"
gcloud pubsub subscriptions create "subscription${RUN_ID}" --topic "topic${RUN_ID}" --project "$TEST_PROJECT"
bq mk --dataset "${TEST_PROJECT}:dataset${RUN_ID}"
bq mk --table "${TEST_PROJECT}:dataset${RUN_ID}.table${RUN_ID}"
gsutil mb -p $TEST_PROJECT "gs://bucket${RUN_ID}"

# It takes time before labels are available to be read by "describe".
#
# jq -e generates exit code 1 on failure. Since we set -e, the script will fail appropriately if the value is not found

sleep 20

DESCRIBE_FLAGS=(--project "$TEST_PROJECT" --format json)
JQ=(jq -e ".labels.${RUN_ID}_name")

#From now on , don't exit on test failure
set +e
gcloud pubsub topics describe "topic${RUN_ID}" "${DESCRIBE_FLAGS[@]}" | "${JQ[@]}"
if [[ $? -ne 0 ]]; then ERROR=1 ; fi
gcloud pubsub subscriptions describe "subscription${RUN_ID}" "${DESCRIBE_FLAGS[@]}" | "${JQ[@]}"
if [[ $? -ne 0 ]]; then ERROR=1 ; fi
bq show --format=json "${TEST_PROJECT}:dataset${RUN_ID}" | "${JQ[@]}"
if [[ $? -ne 0 ]]; then ERROR=1 ; fi
bq show --format=json "${TEST_PROJECT}:dataset${RUN_ID}.table${RUN_ID}" | "${JQ[@]}"
if [[ $? -ne 0 ]]; then ERROR=1 ; fi
# Re Cloud Storage, note:
# 1. For buckets, JSON shows labels without the wrapper  label:{} seen in the others.
# 2. To do a test of labels that are specific to a resource type, in this test we
# defined labels starting gcs, just for buckets.

gsutil label get "gs://bucket${RUN_ID}"| jq -e ".gcs${RUN_ID}_name"
if [[ $? -ne 0 ]]; then ERROR=1 ; fi
gcloud compute instances describe "instance${RUN_ID}" --zone $GCE_ZONE "${DESCRIBE_FLAGS[@]}" | "${JQ[@]}"
if [[ $? -ne 0 ]]; then ERROR=1 ; fi
gcloud compute disks describe "disk${RUN_ID}" --zone $GCE_ZONE "${DESCRIBE_FLAGS[@]}" | "${JQ[@]}"
if [[ $? -ne 0 ]]; then ERROR=1 ; fi
gcloud compute snapshots describe "snapshot${RUN_ID}" "${DESCRIBE_FLAGS[@]}" | "${JQ[@]}"
if [[ $? -ne 0 ]]; then ERROR=1 ; fi

if [ $ERROR -ne 0 ];
then
  # On Error during "describe", we leave resources -- we do not delete them
  trap - EXIT
  # But still, revert the config
  revert_config
  exit $ERROR
fi

