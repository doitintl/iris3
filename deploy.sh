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

SHELL_DETECTION=$(ps -p $$ -oargs= )

if [[ ! "$SHELL_DETECTION" == *bash* ]]; then
  echo >&2 "Need Bash. Found \"$SHELL_DETECTION\""
  exit 1
else
  echo ""
fi

if [[ "$BASH_VERSION" == 3. ]]; then
  echo >&2 "Need Bash version 4 and up. Now $BASH_VERSION"
  exit 1
fi

export PYTHONPATH="."
python3 ./util/check_version.py


START=$(date "+%s")
ROLEID=iris3

REGION=us-central
GAE_REGION_ABBREV=uc

LOGS_TOPIC=iris_logs_topic
SCHEDULELABELING_TOPIC=iris_schedulelabeling_topic
LOG_SINK=iris_log
DEADLETTER_TOPIC=iris_deadletter_topic
DEADLETTER_SUB=iris_deadletter
DO_LABEL_SUBSCRIPTION=do_label
LABEL_ONE_SUBSCRIPTION=label_one

ACK_DEADLINE=60
MAX_DELIVERY_ATTEMPTS=5
MIN_RETRY=60s
MAX_RETRY=600s

if [[ $# -eq 0 ]]; then
  echo Missing project id argument. Run with --help switch for usage.
  exit
fi

PROJECT_ID=$1
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format json|jq -r '.projectNumber')

shift

CRON_ONLY=
while getopts c opt; do
  case $opt in
  c)
    CRON_ONLY=true
    ;;
  *)
    cat <<EOF
      Usage deploy.sh PROJECT_ID [-c]
          Argument:
                  The project to which Iris 3 will be deployed
          Options:
                  -c (at end of line, after project ID):
                      Use only Cloud Scheduler cron to add labels; do not add labels on resource creation.
          Environment variable:
                  GAEVERSION (Optional) sets the Google App Engine Version.
EOF
    exit 1
    ;;
  esac
done

gcloud projects describe "$PROJECT_ID" || {
  echo "Project $PROJECT_ID not found"
  exit 1
}

echo "Project ID $PROJECT_ID"
gcloud config set project "$PROJECT_ID"

GAE_SVC=$(grep "service:" app.yaml | awk '{print $2}')
PUBSUB_VERIFICATION_TOKEN=$(grep "pubsub_verification_token:" config.yaml | awk '{print $2}')
LABEL_ONE_SUBSCRIPTION_ENDPOINT="https://${GAE_SVC}-dot-${PROJECT_ID}.${GAE_REGION_ABBREV}.r.appspot.com/label_one?token=${PUBSUB_VERIFICATION_TOKEN}"
DO_LABEL_SUBSCRIPTION_ENDPOINT="https://${GAE_SVC}-dot-${PROJECT_ID}.${GAE_REGION_ABBREV}.r.appspot.com/do_label?token=${PUBSUB_VERIFICATION_TOKEN}"

declare -A enabled_services
while read -r svc _; do
  # Using the associative array as a set. The value does not matter, just that we can check that a key is in it.
  enabled_services["$svc"]=yes
done < <(gcloud services list | tail -n +2)

required_svcs=(
  cloudresourcemanager.googleapis.com
  pubsub.googleapis.com
  compute.googleapis.com
  bigtable.googleapis.com
  bigtableadmin.googleapis.com
  storage-component.googleapis.com
  sql-component.googleapis.com
  sqladmin.googleapis.com
)
for svc in "${required_svcs[@]}"; do
  if ! [ ${enabled_services["$svc"]+_} ]; then
    gcloud services enable "$svc"
  fi
done

# Get organization id for this project
ORGID=$(curl -X POST -H "Authorization: Bearer \"$(gcloud auth print-access-token)\"" \
  -H "Content-Type: application/json; charset=utf-8" \
  https://cloudresourcemanager.googleapis.com/v1/projects/"${PROJECT_ID}":getAncestry | grep -A 1 organization |
  tail -n 1 | tr -d ' ' | cut -d'"' -f4)

# Create App Engine app
gcloud app describe >&/dev/null || gcloud app create --region=$REGION

# Create custom role to run iris
if gcloud iam roles describe "$ROLEID" --organization "$ORGID"; then
  gcloud iam roles update -q "$ROLEID" --organization "$ORGID" --file roles.yaml
else
  gcloud iam roles create "$ROLEID" -q --organization "$ORGID" --file roles.yaml
fi

# Assign default iris app engine service account with role on organization level
gcloud organizations add-iam-policy-binding "$ORGID" \
  --member "serviceAccount:$PROJECT_ID@appspot.gserviceaccount.com" \
  --role "organizations/$ORGID/roles/$ROLEID" \
  --condition=None

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

PUBSUB_SERVICE_ACCOUNT="service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"

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
 # TODO avoid repetition here and in similar create-or-update cases
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
  gcloud pubsub subscriptions delete "$LABEL_ONE_SUBSCRIPTION" --project="$PROJECT_ID" 2>/dev/null || true
  gcloud pubsub topics delete "$LOGS_TOPIC" --project="$PROJECT_ID" 2>/dev/null || true
else
  # Create PubSub topic for receiving logs about new GCP objects
  gcloud pubsub topics describe "$LOGS_TOPIC" --project="$PROJECT_ID" ||
    gcloud pubsub topics create $LOGS_TOPIC --project="$PROJECT_ID" --quiet >/dev/null

  # Create or update PubSub subscription for receiving log about new GCP objects
  set +e
  gcloud pubsub subscriptions describe "$LABEL_ONE_SUBSCRIPTION" --project="$PROJECT_ID"
  if [[ $? -eq 0 ]]; then
      set -e
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
      set -e
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

  log_filter=("")

  # Add included-projects filter if such is defined, to the log sink
  export PYTHONPATH="."
  included_projects_line=$(python3 ./util/print_included_projects.py)

  if [ -n "$included_projects_line" ]; then
    log_filter+=('logName:(')
    or_=""

    # shellcheck disable=SC2207
    # because  zsh uses read -A and bash uses read -a
    supported_projects_arr=($(echo "${included_projects_line}"))
    for p in "${supported_projects_arr[@]}"; do
      log_filter+=("${or_}\"projects/${p}/logs/\"")
      or_='OR '
    done
    log_filter+=(') AND ')
  fi

  # Add methodName filter to the log sink
  log_filter+=('protoPayload.methodName:(')
  log_filter+=('"storage.buckets.create"')
  log_filter+=('OR "compute.instances.insert" OR "compute.instances.start" OR "datasetservice.insert"')
  log_filter+=('OR "tableservice.insert" OR "google.bigtable.admin.v2.BigtableInstanceAdmin.CreateInstance"')
  log_filter+=('OR "cloudsql.instances.create" OR "v1.compute.disks.insert" OR "v1.compute.disks.createSnapshot"')
  log_filter+=('OR "google.pubsub.v1.Subscriber.CreateSubscription"')
  log_filter+=('OR "google.pubsub.v1.Publisher.CreateTopic"')
  log_filter+=(')')

  # Create or update a sink at org level
  if ! gcloud logging sinks describe --organization="$ORGID" "$LOG_SINK" >&/dev/null; then
    gcloud logging sinks create "$LOG_SINK" \
      pubsub.googleapis.com/projects/"$PROJECT_ID"/topics/"$LOGS_TOPIC" \
      --organization="$ORGID" --include-children \
      --log-filter="${log_filter[*]}" --quiet
  else
    gcloud logging sinks update "$LOG_SINK" \
      pubsub.googleapis.com/projects/"$PROJECT_ID"/topics/"$LOGS_TOPIC" \
      --organization="$ORGID" \
      --log-filter="${log_filter[*]}" --quiet
  fi

  # Extract service account from sink configuration.
  # This is the service account that publishes to PubSub.
  svcaccount=$(gcloud logging sinks describe --organization="$ORGID" "$LOG_SINK" |
    grep writerIdentity | awk '{print $2}')

  # Assign a publisher role to the extracted service account.
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="$svcaccount" --role=roles/pubsub.publisher --quiet
fi

# GAEVERSION might be unbound, so disable this check.
set +u

# Deploy to App Engine
if [[ -n "$GAEVERSION" ]]
then
    gcloud app deploy --project $PROJECT_ID --version $GAEVERSION -q app.yaml cron.yaml
else
    gcloud app deploy --project $PROJECT_ID -q app.yaml cron.yaml
fi
set -u

FINISH=$(date "+%s")
ELAPSED_SEC=$((FINISH - START))
echo >&2 "Elapsed time for $(basename "$0") ${ELAPSED_SEC} s"
