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

ROLEID=iris3

LOG_SINK=iris_log

# Get organization id for this project
ORGID=$(curl -X POST -H "Authorization: Bearer \"$(gcloud auth print-access-token)\"" \
  -H "Content-Type: application/json; charset=utf-8" \
  https://cloudresourcemanager.googleapis.com/v1/projects/"${PROJECT_ID}":getAncestry | grep -A 1 organization |
  tail -n 1 | tr -d ' ' | cut -d'"' -f4)

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


if [[ "$CRON_ONLY" == "true" ]]; then
  echo >&2 "CRON_ONLY set to true."

  gcloud logging sinks delete -q  --organization="$ORGID" "$LOG_SINK" || true
else
  # Create PubSub topic for receiving logs about new GCP objects

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
  #TODO get this directly from the Python class to avoid duplication
  log_filter+=('protoPayload.methodName:(')
  log_filter+=('"storage.buckets.create"')
  log_filter+=('OR "compute.instances.insert" OR "compute.instances.start" OR "datasetservice.insert"')
  log_filter+=('OR "tableservice.insert" ')
  log_filter+=('OR "cloudsql.instances.create" OR "v1.compute.disks.insert" OR "v1.compute.disks.createSnapshot"')
  log_filter+=('OR "v1.compute.snapshots.insert" OR "v1.compute.disks.createSnapshot"')
  log_filter+=('OR "google.pubsub.v1.Subscriber.CreateSubscription"')
  log_filter+=('OR "google.pubsub.v1.Publisher.CreateTopic"')
  log_filter+=(')')

  # Create or update a sink at org level
  if ! gcloud logging sinks describe --organization="$ORGID" "$LOG_SINK" >&/dev/null; then
    echo >&2 "Creating Log Sink/Router at Organization level."
    gcloud logging sinks create "$LOG_SINK" \
      pubsub.googleapis.com/projects/"$PROJECT_ID"/topics/"$LOGS_TOPIC" \
      --organization="$ORGID" --include-children \
      --log-filter="${log_filter[*]}" --quiet
  else
    echo >&2 "Updating Log Sink/Router at Organization level."
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

