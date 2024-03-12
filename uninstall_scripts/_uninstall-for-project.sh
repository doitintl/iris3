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
LABEL_ALL_TOPIC=iris_label_all_topic
DEADLETTER_TOPIC=iris_deadletter_topic
DEADLETTER_SUB=iris_deadletter
DO_LABEL_SUBSCRIPTION=do_label
LABEL_ONE_SUBSCRIPTION=label_one
LABEL_ALL_SUBSCRIPTION=label_all

project_number=$(gcloud projects describe $PROJECT_ID --format json|jq -r '.projectNumber')
PUBSUB_SERVICE_ACCOUNT="service-${project_number}@gcp-sa-pubsub.iam.gserviceaccount.com"

gcloud pubsub topics remove-iam-policy-binding $DEADLETTER_TOPIC \
        --member="serviceAccount:$PUBSUB_SERVICE_ACCOUNT"\
         --role="roles/pubsub.publisher" --project $PROJECT_ID >/dev/null  || true

gcloud pubsub subscriptions remove-iam-policy-binding $DO_LABEL_SUBSCRIPTION \
    --member="serviceAccount:$PUBSUB_SERVICE_ACCOUNT"\
    --role="roles/pubsub.subscriber" --project $PROJECT_ID >/dev/null   || true

gcloud pubsub subscriptions remove-iam-policy-binding $LABEL_ONE_SUBSCRIPTION \
    --member="serviceAccount:$PUBSUB_SERVICE_ACCOUNT"\
    --role="roles/pubsub.subscriber" --project $PROJECT_ID >/dev/null   ||true

gcloud pubsub subscriptions remove-iam-policy-binding $LABEL_ALL_SUBSCRIPTION \
    --member="serviceAccount:$PUBSUB_SERVICE_ACCOUNT"\
    --role="roles/pubsub.subscriber" --project $PROJECT_ID >/dev/null  ||true

# We don't do the following to avoid disrupting PubSub more generally in the project.
#gcloud projects remove-iam-policy-binding ${PROJECT_ID}  \
#    --member="serviceAccount:${PUBSUB_SERVICE_ACCOUNT}"\
#    --role='roles/iam.serviceAccountTokenCreator' ||true

gcloud pubsub subscriptions delete $DEADLETTER_SUB --project="$PROJECT_ID" -q >/dev/null  || true
gcloud pubsub subscriptions delete "$DO_LABEL_SUBSCRIPTION" -q --project="$PROJECT_ID" >/dev/null  || true
gcloud pubsub subscriptions delete "$LABEL_ONE_SUBSCRIPTION" --project="$PROJECT_ID" >/dev/null   || true
gcloud pubsub subscriptions delete "$LABEL_ALL_SUBSCRIPTION" --project="$PROJECT_ID" >/dev/null   || true

gcloud pubsub topics delete "$SCHEDULELABELING_TOPIC" --project="$PROJECT_ID" -q >/dev/null   ||true
gcloud pubsub topics delete "$LABEL_ALL_TOPIC" --project="$PROJECT_ID" -q >/dev/null   || true
gcloud pubsub topics delete "$DEADLETTER_TOPIC" --project="$PROJECT_ID" -q >/dev/null   || true
gcloud pubsub topics delete "$LOGS_TOPIC" --project="$PROJECT_ID"   >/dev/null  || true

gcloud app services delete --project $PROJECT_ID -q iris3  >/dev/null  || true

cp cron_empty.yaml cron.yaml
gcloud app deploy -q cron.yaml -q --project $PROJECT_ID >/dev/null  || true
rm cron.yaml



