#!/usr/bin/env bash
#To uninstall Iris, delete
# * On the org level (see `_deploy-org.sh`), delete
#  * Custom role `iris3`  along with the   policy binding  granting this role to the  built-in App Engine service account `$PROJECT_ID@appspot.gserviceaccount.com`
#  * Log sinks `iris_sink`
#set -x
set -u
set -e


IRIS_CUSTOM_ROLE=$(cat <iris-custom-role.yaml |
       grep "#custom role name"|cut -d":" -f2 | awk '{$1=$1};1')

echo "Iris custom role is \"$IRIS_CUSTOM_ROLE\""

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


