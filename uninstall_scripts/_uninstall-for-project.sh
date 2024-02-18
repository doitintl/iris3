#!/usr/bin/env bash
# This script deletes, on the project level (see `_deploy-project.sh`):
#  * Policy bindings for the topics and subscriptions
#  * Topics and subscriptions
#  * The App Engine service
#  * The Cloud Scheduler cron definition
#set -x
set -u
set -e

SCHEDULELABELING_TOPIC=iris_schedulelabeling_topic
DEADLETTER_TOPIC=iris_deadletter_topic
DEADLETTER_SUB=iris_deadletter
DO_LABEL_SUBSCRIPTION=do_label
LABEL_ONE_SUBSCRIPTION=label_one

project_number=$(gcloud projects describe $PROJECT_ID --format json|jq -r '.projectNumber')
PUBSUB_SERVICE_ACCOUNT="service-${project_number}@gcp-sa-pubsub.iam.gserviceaccount.com"
msg_sender_sa_name=iris-msg-sender
MSGSENDER_SERVICE_ACCOUNT=${msg_sender_sa_name}@${PROJECT_ID}.iam.gserviceaccount.com

gcloud pubsub topics remove-iam-policy-binding $DEADLETTER_TOPIC \
        --member="serviceAccount:$PUBSUB_SERVICE_ACCOUNT"\
         --role="roles/pubsub.publisher" --project $PROJECT_ID >/dev/null || true

gcloud pubsub subscriptions remove-iam-policy-binding $DO_LABEL_SUBSCRIPTION \
    --member="serviceAccount:$PUBSUB_SERVICE_ACCOUNT"\
    --role="roles/pubsub.subscriber" --project $PROJECT_ID || true

gcloud pubsub subscriptions remove-iam-policy-binding $LABEL_ONE_SUBSCRIPTION \
      --member="serviceAccount:$PUBSUB_SERVICE_ACCOUNT"\
      --role="roles/pubsub.subscriber" --project $PROJECT_ID ||true

gcloud projects remove-iam-policy-binding --project ${PROJECT_ID} \
 --member="serviceAccount:${MSGSENDER_SERVICE_ACCOUNT}"\
 --role='roles/iam.serviceAccountTokenCreator'


gcloud pubsub subscriptions delete $DEADLETTER_SUB --project="$PROJECT_ID" -q || true
gcloud pubsub subscriptions delete "$DO_LABEL_SUBSCRIPTION" -q --project="$PROJECT_ID" ||true
gcloud pubsub subscriptions delete "$LABEL_ONE_SUBSCRIPTION" --project="$PROJECT_ID" 2>/dev/null || true

gcloud pubsub topics delete "$SCHEDULELABELING_TOPIC" --project="$PROJECT_ID" -q ||true
gcloud pubsub topics delete "$DEADLETTER_TOPIC" --project="$PROJECT_ID" -q || true
gcloud pubsub topics delete "$LOGS_TOPIC" --project="$PROJECT_ID" 2>/dev/null || true

gcloud app services delete --project $PROJECT_ID -q iris3  ||true

cp cron_empty.yaml cron.yaml
gcloud app deploy -q cron.yaml -q --project $PROJECT_ID  || true
rm cron.yaml



