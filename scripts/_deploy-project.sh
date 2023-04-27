#!/usr/bin/env bash
#
# Deploys Iris to Google App Engine, setting up Roles, Sinks, Topics, and Subscriptions as needed.
# Usage
# - Pass the project as the first command line argument.
# - Optionally set environment variable GAEVERSION to set the Google App Engine Version.
#

set -x
set -u
set -e

GAE_REGION_ABBREV=uc

SCHEDULELABELING_TOPIC=iris_schedulelabeling_topic
DEADLETTER_TOPIC=iris_deadletter_topic
DEADLETTER_SUB=iris_deadletter
DO_LABEL_SUBSCRIPTION=do_label
LABEL_ONE_SUBSCRIPTION=label_one

ACK_DEADLINE=60
MAX_DELIVERY_ATTEMPTS=10
MIN_RETRY=30s
MAX_RETRY=600s

# Must have one of these config (meanwhile, config-dev.yaml is only for local use)
if [[ ! -f "config-test.yaml" ]]  && [[ ! -f "config.yaml" ]]; then
       echo >&2 "config.yaml Must have either config.yaml (use config.yaml.original as an example) or config-test.yaml"
       exit 1
fi


GAE_SVC=$(grep "service:" app.yaml | awk '{print $2}')
# The following line depends on the  the export PYTHON_PATH="." above.
PUBSUB_VERIFICATION_TOKEN=$(python3 ./util/print_pubsub_token.py)
LABEL_ONE_SUBSCRIPTION_ENDPOINT="https://${GAE_SVC}-dot-${PROJECT_ID}.${GAE_REGION_ABBREV}.r.appspot.com/label_one?token=${PUBSUB_VERIFICATION_TOKEN}"
DO_LABEL_SUBSCRIPTION_ENDPOINT="https://${GAE_SVC}-dot-${PROJECT_ID}.${GAE_REGION_ABBREV}.r.appspot.com/do_label?token=${PUBSUB_VERIFICATION_TOKEN}"

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


# Create App Engine app
gcloud app describe >&/dev/null || gcloud app create --region=$REGION


# Create PubSub topic for receiving commands from the /schedule handler that is triggered from cron
gcloud pubsub topics describe "$SCHEDULELABELING_TOPIC" --project="$PROJECT_ID" ||
  gcloud pubsub topics create "$SCHEDULELABELING_TOPIC" --project="$PROJECT_ID" --quiet >/dev/null

# Create PubSub topic for receiving dead messages
gcloud pubsub topics describe "$DEADLETTER_TOPIC" --project="$PROJECT_ID" ||
  gcloud pubsub topics create "$DEADLETTER_TOPIC" --project="$PROJECT_ID" --quiet >/dev/null


# Create or update PubSub subscription for receiving dead messages.
# The messages will just accumulate until pulled, up to message-retention-duratiobn.
# Devops can just look at the stats, or pull messages as needed.
set +e
gcloud pubsub subscriptions describe "$DEADLETTER_SUB" --project="$PROJECT_ID"
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

# Allow Pubsub to publish into the deadletter topic
gcloud pubsub topics add-iam-policy-binding $DEADLETTER_TOPIC \
        --member="serviceAccount:$PUBSUB_SERVICE_ACCOUNT"\
         --role="roles/pubsub.publisher" --project $PROJECT_ID

# Create PubSub subscription receiving commands from the /schedule handler that is triggered from cron
# If the subscription exists, it will not be changed.
# So, if you want to change the PubSub token, you have to manually delete this subscription first.
set +e
gcloud pubsub subscriptions describe "$DO_LABEL_SUBSCRIPTION" --project="$PROJECT_ID"
if [[ $? -eq 0 ]]; then
  set -e
  echo >&2 "Updating $DO_LABEL_SUBSCRIPTION"

  gcloud pubsub subscriptions update "$DO_LABEL_SUBSCRIPTION" \
    --project="$PROJECT_ID" \
    --push-endpoint "$DO_LABEL_SUBSCRIPTION_ENDPOINT" \
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
    --ack-deadline=$ACK_DEADLINE \
    --max-delivery-attempts=$MAX_DELIVERY_ATTEMPTS \
    --dead-letter-topic=$DEADLETTER_TOPIC \
    --min-retry-delay=$MIN_RETRY \
    --max-retry-delay=$MAX_RETRY \
    --quiet >/dev/null
fi


# Allow Pubsub to delete failed message from this sub
gcloud pubsub subscriptions add-iam-policy-binding $DO_LABEL_SUBSCRIPTION \
    --member="serviceAccount:$PUBSUB_SERVICE_ACCOUNT"\
    --role="roles/pubsub.subscriber" --project $PROJECT_ID


if [[ "$CRON_ONLY" == "true" ]]; then
  echo >&2 "CRON_ONLY set to true."
  gcloud pubsub subscriptions delete "$LABEL_ONE_SUBSCRIPTION" --project="$PROJECT_ID" 2>/dev/null || true
  gcloud pubsub topics delete "$LOGS_TOPIC" --project="$PROJECT_ID" 2>/dev/null || true
else
  # Create PubSub topic for receiving logs about new GCP objects
  gcloud pubsub topics describe "$LOGS_TOPIC" --project="$PROJECT_ID" ||
    gcloud pubsub topics create $LOGS_TOPIC --project="$PROJECT_ID" --quiet >/dev/null

  # Create or update PubSub subscription for receiving log about new GCP objects
  set +e
  gcloud pubsub subscriptions describe "$LABEL_ONE_SUBSCRIPTION" --project="$PROJECT_ID"
  label_one_subsc_exists=$?
  set -e
  if [[ $label_one_subsc_exists -eq 0 ]]; then
      echo >&2 "Updating $LABEL_ONE_SUBSCRIPTION"
      gcloud pubsub subscriptions update "$LABEL_ONE_SUBSCRIPTION" --project="$PROJECT_ID" \
        --push-endpoint="$LABEL_ONE_SUBSCRIPTION_ENDPOINT" \
        --ack-deadline=$ACK_DEADLINE \
        --max-delivery-attempts=$MAX_DELIVERY_ATTEMPTS \
        --dead-letter-topic=$DEADLETTER_TOPIC \
        --min-retry-delay=$MIN_RETRY \
        --max-retry-delay=$MAX_RETRY \
        --quiet >/dev/null
  else
      gcloud pubsub subscriptions create "$LABEL_ONE_SUBSCRIPTION" --topic "$LOGS_TOPIC" --project="$PROJECT_ID" \
        --push-endpoint="$LABEL_ONE_SUBSCRIPTION_ENDPOINT" \
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
      --role="roles/pubsub.subscriber" --project $PROJECT_ID
fi


# GAEVERSION might be unbound, so disable this -u check.
set +u

# Deploy to App Engine
if [[ -n "$GAEVERSION" ]]
then
    gcloud app deploy --project $PROJECT_ID --version $GAEVERSION -q app.yaml cron.yaml
else
    gcloud app deploy --project $PROJECT_ID -q app.yaml cron.yaml
fi

set -u

