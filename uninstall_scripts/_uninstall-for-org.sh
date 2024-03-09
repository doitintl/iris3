#!/usr/bin/env bash
# This script deletes, on the org level (see `_deploy-org.sh`):
#  * Iris Custom role   along with the policy binding  granting this role to the  built-in App Engine service account `$PROJECT_ID@appspot.gserviceaccount.com`
#  * Log sinks `iris_sink`
set -x

# The following line must come before set -u
if [[ -z "$IRIS_CUSTOM_ROLE" ]]; then IRIS_CUSTOM_ROLE=iris3; fi
if [[ -z "$SKIP_ADDING_IAM_BINDINGS" ]]; then SKIP_ADDING_IAM_BINDINGS=""; fi

set -u
set -e



LOG_SINK=iris_log

ORGID=$(gcloud projects get-ancestors "${PROJECT_ID}" | grep organization |tr -s ' ' |cut -d' ' -f1)

gcloud organizations remove-iam-policy-binding "$ORGID" --all \
  --member "serviceAccount:$PROJECT_ID@appspot.gserviceaccount.com" \
  --role "organizations/$ORGID/roles/$IRIS_CUSTOM_ROLE" >/dev/null|| true

gcloud iam roles delete -q "$IRIS_CUSTOM_ROLE" --organization "$ORGID" >/dev/null || true


if  gcloud logging sinks describe --organization="$ORGID" "$LOG_SINK" >&/dev/null; then
    svcaccount=$(gcloud logging sinks describe --organization="$ORGID" "$LOG_SINK" |
      grep writerIdentity | awk '{print $2}')

    gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
      --member="$svcaccount" --role=roles/pubsub.publisher -q >/dev/null ||true

    gcloud logging sinks delete -q --organization="$ORGID" "$LOG_SINK" || true

fi


