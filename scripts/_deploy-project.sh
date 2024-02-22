#!/usr/bin/env bash
#
# Deploys Iris to Google App Engine,
# first setting up Sinks, Topics, Subscriptions, and Role Bindings as needed.
# Usage
# - Called from deploy.sh
# - Pass the project as the first command line argument.
#

#set -x
set -u
set -e

SCHEDULELABELING_TOPIC=iris_schedulelabeling_topic
DEADLETTER_TOPIC=iris_deadletter_topic
DEADLETTER_SUB=iris_deadletter
DO_LABEL_SUBSCRIPTION=do_label
LABEL_ONE_SUBSCRIPTION=label_one

ACK_DEADLINE=60
MAX_DELIVERY_ATTEMPTS=10
MIN_RETRY=30s
MAX_RETRY=600s

# Must have one of these config
if [[ ! -f "config-test.yaml" ]]  && [[ ! -f "config.yaml" ]]; then
       echo >&2 "config.yaml Must have either config.yaml (use config.yaml.original as an example) or config-test.yaml"
       exit 1
fi

appengineHostname=$(gcloud app describe --project $PROJECT_ID | grep defaultHostname |cut -d":" -f2 | awk '{$1=$1};1' )
if [[ -z "$appengineHostname" ]]; then
   echo >&2 "App Engine is not enabled in $PROJECT_ID.
   To do this, please deploy a simple \"Hello World\" default service to enable App Engine.
   In doing so, select the App Engine region that you prefer. It is immutable."

   exit 1
fi

gae_svc=$(grep "service:" app.yaml | awk '{print $2}')


LABEL_ONE_SUBSCRIPTION_ENDPOINT="https://${gae_svc}-dot-${appengineHostname}/label_one"
DO_LABEL_SUBSCRIPTION_ENDPOINT="https://${gae_svc}-dot-${appengineHostname}/do_label?token"

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
)
for svc in "${required_svcs[@]}"; do
  if ! [ ${enabled_services["$svc"]+_} ]; then
    gcloud services enable "$svc"
  fi
done


# Create PubSub topic for receiving commands from the /schedule handler that is triggered from cron
gcloud pubsub topics describe "$SCHEDULELABELING_TOPIC" --project="$PROJECT_ID" &> /dev/null ||
  gcloud pubsub topics create "$SCHEDULELABELING_TOPIC" --project="$PROJECT_ID" --quiet >/dev/null

# Create PubSub topic for receiving dead messages
gcloud pubsub topics describe "$DEADLETTER_TOPIC" --project="$PROJECT_ID" &> /dev/null  ||
  gcloud pubsub topics create "$DEADLETTER_TOPIC" --project="$PROJECT_ID" --quiet >/dev/null


# Create or update PubSub subscription for receiving dead messages.
# The messages will just accumulate until pulled, up to message-retention-duration.
# Devops can just look at the stats, or pull messages as needed.
set +e
gcloud pubsub subscriptions describe "$DEADLETTER_SUB" --project="$PROJECT_ID" &> /dev/null

if [[ $? -eq 0 ]]; then
   set -e
   echo >&2 "Updating $DEADLETTER_SUB"
   gcloud pubsub subscriptions update $DEADLETTER_SUB \
   --project="$PROJECT_ID" \
   --message-retention-duration=2d \
   --quiet >/dev/null
else
   set -e
   gcloud pubsub subscriptions create $DEADLETTER_SUB \
   --project="$PROJECT_ID" \
   --topic $DEADLETTER_TOPIC \
   --message-retention-duration=2d \
   --quiet >/dev/null
fi

project_number=$(gcloud projects describe $PROJECT_ID --format json|jq -r '.projectNumber')
PUBSUB_SERVICE_ACCOUNT="service-${project_number}@gcp-sa-pubsub.iam.gserviceaccount.com"

msg_sender_sa_name=iris-msg-sender

set +e
gcloud iam service-accounts describe  ${msg_sender_sa_name}@${PROJECT_ID}.iam.gserviceaccount.com --project $PROJECT_ID
if [[ $? -ne 0 ]]; then
  set -e
  gcloud iam service-accounts create --project $PROJECT_ID $msg_sender_sa_name
fi
set -e

MSGSENDER_SERVICE_ACCOUNT=${msg_sender_sa_name}@${PROJECT_ID}.iam.gserviceaccount.com

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
 --member="serviceAccount:${PUBSUB_SERVICE_ACCOUNT}"\
 --role='roles/iam.serviceAccountTokenCreator'

set +e
# Allow Pubsub to publish into the deadletter topic
BINDING_ERR_OUTPUT=$(gcloud pubsub topics add-iam-policy-binding $DEADLETTER_TOPIC \
        --member="serviceAccount:$PUBSUB_SERVICE_ACCOUNT"\
         --role="roles/pubsub.publisher" --project $PROJECT_ID 2>&1 )
if [[ $? -ne 0  && $BINDING_ERR_OUTPUT == *"gcp-sa-pubsub.iam.gserviceaccount.com does not exist."* ]]; then
  # Sometimes the PubSub svc account (service-99999999999@gcp-sa-pubsub.iam.gserviceaccount.com)
  # does not exist on new projects. I don't know why.
  # Note that this svc account is NOT in the user project;
  # it can be thought of as existing in a hidden Google-controlled project.
  gcloud beta  services identity create --project $PROJECT_ID --service pubsub

  set -e
  #Redo the above binding command
  gcloud pubsub topics add-iam-policy-binding $DEADLETTER_TOPIC \
          --member="serviceAccount:$PUBSUB_SERVICE_ACCOUNT"\
           --role="roles/pubsub.publisher" --project $PROJECT_ID >/dev/null

fi
set -e

# Create PubSub subscription receiving commands from the /schedule handler that is triggered from cron
# If the subscription exists, it will not be changed.
# So, if you want to change the PubSub token, you have to manually delete this subscription first.
set +e
gcloud pubsub subscriptions describe "$DO_LABEL_SUBSCRIPTION" --project="$PROJECT_ID" &>/dev/null
if [[ $? -eq 0 ]]; then
  set -e
  echo >&2 "Updating $DO_LABEL_SUBSCRIPTION"

  gcloud pubsub subscriptions update "$DO_LABEL_SUBSCRIPTION" \
    --project="$PROJECT_ID" \
    --push-endpoint "$DO_LABEL_SUBSCRIPTION_ENDPOINT" \
    --push-auth-service-account $MSGSENDER_SERVICE_ACCOUNT  \
    --ack-deadline=$ACK_DEADLINE \
    --max-delivery-attempts=$MAX_DELIVERY_ATTEMPTS \
    --dead-letter-topic=$DEADLETTER_TOPIC \
    --min-retry-delay=$MIN_RETRY \
    --max-retry-delay=$MAX_RETRY \
    --quiet >/dev/null
else
  set -e
  gcloud pubsub subscriptions create "$DO_LABEL_SUBSCRIPTION" \
    --topic "$SCHEDULELABELING_TOPIC" --project="$PROJECT_ID" \
    --push-endpoint "$DO_LABEL_SUBSCRIPTION_ENDPOINT" \
    --push-auth-service-account $MSGSENDER_SERVICE_ACCOUNT  \
    --ack-deadline=$ACK_DEADLINE \
    --max-delivery-attempts=$MAX_DELIVERY_ATTEMPTS \
    --dead-letter-topic=$DEADLETTER_TOPIC \
    --min-retry-delay=$MIN_RETRY \
    --max-retry-delay=$MAX_RETRY \
    --quiet >/dev/null
fi

# Allow Pubsub to delete failed message from this sub
gcloud pubsub subscriptions add-iam-policy-binding $DO_LABEL_SUBSCRIPTION \
    --member="serviceAccount:$PUBSUB_SERVICE_ACCOUNT" \
    --role="roles/pubsub.subscriber" --project $PROJECT_ID >/dev/null

if [[ "$LABEL_ON_CREATION_EVENT" != "true" ]]; then
  echo >&2 "Will not label on creation event."
  gcloud pubsub subscriptions delete "$LABEL_ONE_SUBSCRIPTION" --project="$PROJECT_ID" 2>/dev/null || true
  gcloud pubsub topics delete "$LOGS_TOPIC" --project="$PROJECT_ID" 2>/dev/null || true
else
  # Create PubSub topic for receiving logs about new GCP objects
  gcloud pubsub topics describe "$LOGS_TOPIC" --project="$PROJECT_ID" &>/dev/null ||
    gcloud pubsub topics create $LOGS_TOPIC --project="$PROJECT_ID" --quiet >/dev/null

  # Create or update PubSub subscription for receiving log about new GCP objects
  set +e
  gcloud pubsub subscriptions describe "$LABEL_ONE_SUBSCRIPTION" --project="$PROJECT_ID" &>/dev/null
  label_one_subsc_exists=$?
  set -e
  if [[ $label_one_subsc_exists -eq 0 ]]; then
      echo >&2 "Updating $LABEL_ONE_SUBSCRIPTION"
      gcloud pubsub subscriptions update "$LABEL_ONE_SUBSCRIPTION" --project="$PROJECT_ID" \
        --push-endpoint="$LABEL_ONE_SUBSCRIPTION_ENDPOINT" \
        --push-auth-service-account $MSGSENDER_SERVICE_ACCOUNT  \
        --ack-deadline=$ACK_DEADLINE \
        --max-delivery-attempts=$MAX_DELIVERY_ATTEMPTS \
        --dead-letter-topic=$DEADLETTER_TOPIC \
        --min-retry-delay=$MIN_RETRY \
        --max-retry-delay=$MAX_RETRY \
        --quiet >/dev/null
  else
      gcloud pubsub subscriptions create "$LABEL_ONE_SUBSCRIPTION" \
         --topic "$LOGS_TOPIC" --project="$PROJECT_ID" \
        --push-endpoint="$LABEL_ONE_SUBSCRIPTION_ENDPOINT" \
        --push-auth-service-account $MSGSENDER_SERVICE_ACCOUNT  \
        --ack-deadline=$ACK_DEADLINE \
        --max-delivery-attempts=$MAX_DELIVERY_ATTEMPTS \
        --dead-letter-topic=$DEADLETTER_TOPIC \
        --min-retry-delay=$MIN_RETRY \
        --max-retry-delay=$MAX_RETRY \
        --quiet >/dev/null
  fi

  # Allow Pubsub to delete failed message from this sub
  gcloud pubsub subscriptions add-iam-policy-binding $LABEL_ONE_SUBSCRIPTION \
      --member="serviceAccount:$PUBSUB_SERVICE_ACCOUNT"\
      --role="roles/pubsub.subscriber" --project $PROJECT_ID >/dev/null
fi



if [[ "$LABEL_ON_CRON" == "true" ]]; then
    cp cron_full.yaml cron.yaml
else
   echo >&2 "Will not have a Cloud Scheduler schedule"
   cp cron_empty.yaml cron.yaml
fi

gcloud app deploy --project $PROJECT_ID --quiet app.yaml cron.yaml

rm cron.yaml # In this script, cron.yaml is a temp file, a copy of  cron_full.yaml or cron_empty.yaml