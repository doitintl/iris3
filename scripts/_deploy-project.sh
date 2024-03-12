#!/usr/bin/env bash
#
# Deploys Iris to Google App Engine,
# first setting up Sinks, Topics, Subscriptions, and Role Bindings as needed.
# Usage
# - Called from deploy.sh
# - Pass the project as the first command line argument.
#

#set -x
# The following must come before set -u
if [[ -z "$SKIP_ADDING_IAM_BINDINGS" ]]; then SKIP_ADDING_IAM_BINDINGS=""; fi
set -u
set -e

SCHEDULELABELING_TOPIC=iris_schedulelabeling_topic
LABEL_ALL_TOPIC=iris_label_all_topic
DEADLETTER_TOPIC=iris_deadletter_topic
DEADLETTER_SUB=iris_deadletter
DO_LABEL_SUBSCRIPTION=do_label
LABEL_ONE_SUBSCRIPTION=label_one
LABEL_ALL_SUBSCRIPTION=label_all

ACK_DEADLINE=60
MAX_DELIVERY_ATTEMPTS=10
MIN_RETRY=30s
MAX_RETRY=600s

# Must have one of these config
if [[ ! -f "config-test.yaml" ]] && [[ ! -f "config.yaml" ]]; then
  echo >&2 "config.yaml Must have either config.yaml (use config.yaml.original as an example) or config-test.yaml"
  exit 1
fi

#Next line duplicate of our Python func gae_url_with_multiregion_abbrev
appengineHostname=$(gcloud app describe --project $PROJECT_ID | grep defaultHostname | cut -d":" -f2 | awk '{$1=$1};1')
if [[ -z "$appengineHostname" ]]; then
  echo "App Engine is not enabled in $PROJECT_ID.
   To do this, please enable it with \"gcloud app create [--region=REGION]\",
   and then deploy a simple \"Hello World\" default service to enable App Engine."
  exit 1
fi

appengine_sa_has_editor_role=$(gcloud projects get-iam-policy ${PROJECT_ID} \
  --flatten="bindings[].members" \
  --format='table(bindings.role)' \
  --filter="bindings.members:${PROJECT_ID}@appspot.gserviceaccount.com" | grep "roles/editor" || true)

if [ -z "$appengine_sa_has_editor_role" ]; then
  echo "Must bind role Project Editor for project ${PROJECT_ID} to service account ${PROJECT_ID}@appspot.gserviceaccount.com.
      (The binding exists by default but is missing.)"
  exit 1
fi

gae_svc=$(grep "service:" app.yaml | awk '{print $2}')

LABEL_ONE_SUBSCRIPTION_ENDPOINT="https://${gae_svc}-dot-${appengineHostname}/label_one"
DO_LABEL_SUBSCRIPTION_ENDPOINT="https://${gae_svc}-dot-${appengineHostname}/do_label"
LABEL_ALL_SUBSCRIPTION_ENDPOINT="https://${gae_svc}-dot-${appengineHostname}/label_all"

# The following code to enable service is only needed on first deployment, and so slows things
# down unnecessarily otherwise. But most users do not install Iris repeatedly.
declare -A enabled_services
while read -r svc _; do
  # We check that a key is in the associative array, treating it as a set.
  # The value (which is always "yes") does not matter, just that it exists as a key.
  enabled_services["$svc"]=yes
done < <(gcloud services list --format="value(config.name)")

required_svcs=(
  cloudscheduler.googleapis.com
  cloudresourcemanager.googleapis.com
  pubsub.googleapis.com
  compute.googleapis.com
  storage-component.googleapis.com
  sql-component.googleapis.com
  sqladmin.googleapis.com
  bigquery.googleapis.com
)
for svc in "${required_svcs[@]}"; do
  if ! [ ${enabled_services["$svc"]+_} ]; then
    gcloud services enable "$svc"
  fi
done

# Create PubSub topic for receiving commands from the /schedule handler that is triggered from cron
gcloud pubsub topics describe "$SCHEDULELABELING_TOPIC" --project="$PROJECT_ID" &>/dev/null ||
  gcloud pubsub topics create "$SCHEDULELABELING_TOPIC" --project="$PROJECT_ID" --quiet >/dev/null

# Create PubSub topic for receiving dead messages
gcloud pubsub topics describe "$DEADLETTER_TOPIC" --project="$PROJECT_ID" &>/dev/null ||
  gcloud pubsub topics create "$DEADLETTER_TOPIC" --project="$PROJECT_ID" --quiet >/dev/null

# Create or update PubSub subscription for receiving dead messages.
# The messages will just accumulate until pulled, up to message-retention-duration.
# Devops can just look at the stats, or pull messages as needed.

if gcloud pubsub subscriptions describe "$DEADLETTER_SUB" --project="$PROJECT_ID" &>/dev/null; then
    gcloud pubsub subscriptions update $DEADLETTER_SUB \
    --project="$PROJECT_ID" \
    --message-retention-duration=2d \
    --quiet >/dev/null 2>&1

else
   gcloud pubsub subscriptions create $DEADLETTER_SUB \
    --project="$PROJECT_ID" \
    --topic $DEADLETTER_TOPIC \
    --message-retention-duration=2d \
    --quiet >/dev/null 2>&1
fi

project_number=$(gcloud projects describe $PROJECT_ID --format json | jq -r '.projectNumber')
PUBSUB_SERVICE_ACCOUNT="service-${project_number}@gcp-sa-pubsub.iam.gserviceaccount.com"
# The following line is only needed on first deployment, and so slows things
# down unnecessarily otherwise. But most users do not install Iris repeatedly.
gcloud beta services identity create --project $PROJECT_ID --service pubsub >/dev/null 2>&1

if ! gcloud iam service-accounts describe iris-msg-sender@${PROJECT_ID}.iam.gserviceaccount.com --project $PROJECT_ID >/dev/null ;
then
  gcloud iam service-accounts create --project $PROJECT_ID iris-msg-sender
fi


MSGSENDER_SERVICE_ACCOUNT=iris-msg-sender@${PROJECT_ID}.iam.gserviceaccount.com

# Create PubSub subscription receiving commands from the /schedule handler that is triggered from cron
# If the subscription exists, it will not be changed.
# So, if you want to change the PubSub token, you have to manually delete this subscription first.


if gcloud pubsub subscriptions describe "$DO_LABEL_SUBSCRIPTION" --project="$PROJECT_ID" &>/dev/null ;
then
  gcloud pubsub subscriptions update "$DO_LABEL_SUBSCRIPTION" \
    --project="$PROJECT_ID" \
    --push-endpoint "$DO_LABEL_SUBSCRIPTION_ENDPOINT" \
    --push-auth-service-account $MSGSENDER_SERVICE_ACCOUNT \
    --ack-deadline=$ACK_DEADLINE \
    --max-delivery-attempts=$MAX_DELIVERY_ATTEMPTS \
    --dead-letter-topic=$DEADLETTER_TOPIC \
    --min-retry-delay=$MIN_RETRY \
    --max-retry-delay=$MAX_RETRY \
    --quiet >/dev/null 2>&1
else
  gcloud pubsub subscriptions create "$DO_LABEL_SUBSCRIPTION" \
    --topic "$SCHEDULELABELING_TOPIC" --project="$PROJECT_ID" \
    --push-endpoint "$DO_LABEL_SUBSCRIPTION_ENDPOINT" \
    --push-auth-service-account $MSGSENDER_SERVICE_ACCOUNT \
    --ack-deadline=$ACK_DEADLINE \
    --max-delivery-attempts=$MAX_DELIVERY_ATTEMPTS \
    --dead-letter-topic=$DEADLETTER_TOPIC \
    --min-retry-delay=$MIN_RETRY \
    --max-retry-delay=$MAX_RETRY \
    --quiet >/dev/null 2>&1
fi

if [[ "$LABEL_ON_CREATION_EVENT" != "true" ]];
then
  gcloud pubsub subscriptions delete "$LABEL_ONE_SUBSCRIPTION" --project="$PROJECT_ID" 2>/dev/null || true
  gcloud pubsub topics delete "$LOGS_TOPIC" --project="$PROJECT_ID" 2>/dev/null || true
else
  # Create PubSub topic for receiving logs about new GCP objects
  gcloud pubsub topics describe "$LOGS_TOPIC" --project="$PROJECT_ID" &>/dev/null ||
    gcloud pubsub topics create $LOGS_TOPIC --project="$PROJECT_ID" --quiet >/dev/null 2>&1

  # Create or update PubSub subscription for receiving log about new GCP objects
  if gcloud pubsub subscriptions describe "$LABEL_ONE_SUBSCRIPTION" --project="$PROJECT_ID" &>/dev/null ;
  then
    gcloud pubsub subscriptions update "$LABEL_ONE_SUBSCRIPTION" --project="$PROJECT_ID" \
      --push-endpoint="$LABEL_ONE_SUBSCRIPTION_ENDPOINT" \
      --push-auth-service-account $MSGSENDER_SERVICE_ACCOUNT \
      --ack-deadline=$ACK_DEADLINE \
      --max-delivery-attempts=$MAX_DELIVERY_ATTEMPTS \
      --dead-letter-topic=$DEADLETTER_TOPIC \
      --min-retry-delay=$MIN_RETRY \
      --max-retry-delay=$MAX_RETRY \
      --quiet >/dev/null 2>&1
  else
    gcloud pubsub subscriptions create "$LABEL_ONE_SUBSCRIPTION" \
      --topic "$LOGS_TOPIC" --project="$PROJECT_ID" \
      --push-endpoint="$LABEL_ONE_SUBSCRIPTION_ENDPOINT" \
      --push-auth-service-account $MSGSENDER_SERVICE_ACCOUNT \
      --ack-deadline=$ACK_DEADLINE \
      --max-delivery-attempts=$MAX_DELIVERY_ATTEMPTS \
      --dead-letter-topic=$DEADLETTER_TOPIC \
      --min-retry-delay=$MIN_RETRY \
      --max-retry-delay=$MAX_RETRY \
      --quiet >/dev/null 2>&1
  fi

fi

gcloud pubsub topics describe "$LABEL_ALL_TOPIC" --project="$PROJECT_ID" &>/dev/null ||
  gcloud pubsub topics create $LABEL_ALL_TOPIC --project="$PROJECT_ID" --quiet >/dev/null


if gcloud pubsub subscriptions describe "$LABEL_ALL_SUBSCRIPTION" --project="$PROJECT_ID" &>/dev/null; then
  gcloud pubsub subscriptions update "$LABEL_ALL_SUBSCRIPTION" \
    --project="$PROJECT_ID" \
    --push-endpoint "$LABEL_ALL_SUBSCRIPTION_ENDPOINT" \
    --push-auth-service-account $MSGSENDER_SERVICE_ACCOUNT \
    --ack-deadline=$ACK_DEADLINE \
    --max-delivery-attempts=$MAX_DELIVERY_ATTEMPTS \
    --dead-letter-topic=$DEADLETTER_TOPIC \
    --min-retry-delay=$MIN_RETRY \
    --max-retry-delay=$MAX_RETRY \
    --quiet >/dev/null 2>&1
else
  gcloud pubsub subscriptions create "$LABEL_ALL_SUBSCRIPTION" \
    --topic "$LABEL_ALL_TOPIC" --project="$PROJECT_ID" \
    --push-endpoint "$LABEL_ALL_SUBSCRIPTION_ENDPOINT" \
    --push-auth-service-account $MSGSENDER_SERVICE_ACCOUNT \
    --ack-deadline=$ACK_DEADLINE \
    --max-delivery-attempts=$MAX_DELIVERY_ATTEMPTS \
    --dead-letter-topic=$DEADLETTER_TOPIC \
    --min-retry-delay=$MIN_RETRY \
    --max-retry-delay=$MAX_RETRY \
    --quiet >/dev/null
fi

if [[ "$LABEL_ON_CREATION_EVENT" == "true" ]]; then
  # Allow Pubsub to delete failed message from this sub
  gcloud pubsub subscriptions add-iam-policy-binding $DO_LABEL_SUBSCRIPTION \
    --member="serviceAccount:$PUBSUB_SERVICE_ACCOUNT" \
    --role="roles/pubsub.subscriber" --project $PROJECT_ID >/dev/null 2>&1

fi

gcloud pubsub subscriptions add-iam-policy-binding $LABEL_ALL_SUBSCRIPTION \
  --member="serviceAccount:$PUBSUB_SERVICE_ACCOUNT" \
  --role="roles/pubsub.subscriber" --project $PROJECT_ID >/dev/null 2>&1

# Allow Pubsub to delete failed message from this sub
gcloud pubsub subscriptions add-iam-policy-binding $LABEL_ONE_SUBSCRIPTION \
  --member="serviceAccount:$PUBSUB_SERVICE_ACCOUNT" \
  --role="roles/pubsub.subscriber" --project $PROJECT_ID >/dev/null 2>&1

# Allow Pubsub to publish into the deadletter topic
gcloud pubsub topics add-iam-policy-binding $DEADLETTER_TOPIC \
  --member="serviceAccount:$PUBSUB_SERVICE_ACCOUNT" \
  --role="roles/pubsub.publisher" --project "$PROJECT_ID" >/dev/null 2>&1

if [[ "$SKIP_ADDING_IAM_BINDINGS" != "true" ]]; then
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${PUBSUB_SERVICE_ACCOUNT}" \
    --role='roles/iam.serviceAccountTokenCreator' >/dev/null 2>&1
fi

if [[ "$LABEL_ON_CRON" == "true" ]]; then
  cp cron_full.yaml cron.yaml
else
  cp cron_empty.yaml cron.yaml
fi

gcloud app deploy --project "$PROJECT_ID" --quiet app.yaml cron.yaml

rm cron.yaml # In this script, cron.yaml is a temp file, a copy of cron_full.yaml or cron_empty.yaml
