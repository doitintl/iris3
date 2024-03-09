#!/usr/bin/env bash
#
# Deploys Iris to Google App Engine, setting up Roles, Sinks, Topics, and Subscriptions as needed.
# Usage
# - Called from deploy.sh

set -x
# The following lines must come before set -u
if [[ -z "$IRIS_CUSTOM_ROLE" ]]; then IRIS_CUSTOM_ROLE=iris3; fi
if [[ -z "$SKIP_ADDING_IAM_BINDINGS" ]] ; then SKIP_ADDING_IAM_BINDINGS=""; fi
set -u
set -e

LOG_SINK=iris_log

# Get organization id for this project
ORGID=$(gcloud projects get-ancestors $PROJECT_ID --format='value(TYPE,ID)' | awk '/org/ {print $2}')

set +e
# Create custom role to run iris
existing_role=$(gcloud iam roles describe --organization "$ORGID" $IRIS_CUSTOM_ROLE --format='value(deleted,etag)')
# existing_role variable as follows:
# 1. For soft-deleted role, existing_role is like "True BwYSsZlhISU="
# 2. For active role, without the string True.
# 3. For non-existing role, empty-string
if [ -n "$existing_role" ]; then
  if [[ "$existing_role" == *"True"* ]]; then # It's a soft-deleted role
    gcloud iam roles undelete -q "$IRIS_CUSTOM_ROLE"  --organization "$ORGID"  >/dev/null
  fi

  gcloud iam roles update -q "$IRIS_CUSTOM_ROLE" --organization "$ORGID" --file iris-custom-role.yaml >/dev/null
  role_error=$?

else
    gcloud iam roles create -q "$IRIS_CUSTOM_ROLE"  --organization "$ORGID" --file iris-custom-role.yaml  >/dev/null
    role_error=$?
fi

set -e

if [[ "$role_error" != "0" ]]; then
  echo "Error in accessing organization.
   If you just want to redeploy to the same project,
   e.g., to upgrade the config, and you have the necessary
   project role but not the necessary org role,
   please run ./deploy.sh -p .
   Or get yourself the org-level role as documented in README."
  exit $role_error
fi

# Assign the new custom org-level role to the default App Engine service account for the deployment project
gcloud organizations add-iam-policy-binding "$ORGID" \
  --member "serviceAccount:$PROJECT_ID@appspot.gserviceaccount.com" \
  --role "organizations/$ORGID/roles/$IRIS_CUSTOM_ROLE" \
  --condition=None >/dev/null


if [[ "$LABEL_ON_CREATION_EVENT" != "true" ]]; then
  echo >&2 "Will not label on creation event."
  gcloud logging sinks delete -q --organization="$ORGID" "$LOG_SINK" || true
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
  #TODO Each Python plugin class should expose these and we should pull it from there,to have the info in one place.
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
    #echo >&2 "Creating Log Sink/Router at Organization level."
    gcloud logging sinks create "$LOG_SINK" \
      pubsub.googleapis.com/projects/"$PROJECT_ID"/topics/"$LOGS_TOPIC" \
      --organization="$ORGID" --include-children \
      --log-filter="${log_filter[*]}" --quiet
  else
    #echo >&2 "Updating Log Sink/Router at Organization level."
    gcloud logging sinks update "$LOG_SINK" \
      pubsub.googleapis.com/projects/"$PROJECT_ID"/topics/"$LOGS_TOPIC" \
      --organization="$ORGID" \
      --log-filter="${log_filter[*]}" --quiet
  fi

  # Extract service account from sink configuration.
  # This is the service account that publishes to PubSub.
  svcaccount=$(gcloud logging sinks describe --organization="$ORGID" "$LOG_SINK"  |
    grep writerIdentity | awk '{print $2}')

  if [[ "$SKIP_ADDING_IAM_BINDINGS" != "true" ]]; then
      echo >&2 "Adding IAM bindings in _deploy-org"
    # Assign a publisher role to the extracted service account.
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
      --member="$svcaccount" --role=roles/pubsub.publisher --quiet > /dev/null
  else
    echo >&2 "Not adding IAM bindings in _deploy-org"fi
  fi
fi
