#!/usr/bin/env bash

set -ex

ROLEID=iris

LOGS_TOPIC=iris_logs_topic
SCHEDULED_LABELING_TOPIC=iris_scheduled_labeling_topic
LOGS_SINK_SUB=iris_logs_sub

if [[ $# -eq 0 ]]; then
  echo Missing project id argument
  exit
fi

PROJECTID=$(gcloud projects list | grep -i "^$1 " | awk '{print $1}')

if [ -z "$PROJECTID" ]; then
  echo "Project $1 Not Found!"
  exit 1
fi

echo "Project ID $PROJECTID"
gcloud config set project "$PROJECTID"

declare -A enabled_services
while read -r svc _; do
  enabled_services["$svc"]=yes
done < <(gcloud services list | tail -n +2)

required_svcs=(
  cloudresourcemanager.googleapis.com
  pubsub.googleapis.com
  compute.googleapis.com
  bigtable.googleapis.com
  storage-component.googleapis.com
  sql-component.googleapis.com
  sqladmin.googleapis.com
)

# Enable services if they are not
for svc in "${required_svcs[@]}"; do
  [[ "${enabled_services["$svc"]}" == "yes" ]] || gcloud services enable "$svc"
done

# Get organization id for this project
ORGID=$(curl -X POST -H "Authorization: Bearer \"$(gcloud auth print-access-token)\"" \
  -H "Content-Type: application/json; charset=utf-8" \
  https://cloudresourcemanager.googleapis.com/v1/projects/"${PROJECTID}":getAncestry | grep -A 1 organization |
  tail -n 1 | tr -d ' ' | cut -d'"' -f4)

# Create App Engine app
gcloud app describe >&/dev/null || gcloud app create --region=us-central

# Create custom role to run iris
gcloud iam roles describe "$ROLEID" --organization "$ORGID" ||
  gcloud iam roles create "$ROLEID" --organization "$ORGID" --file roles.yaml

# assign default iris app engine service account with role on organization level
gcloud organizations add-iam-policy-binding "$ORGID" \
  --member "serviceAccount:$PROJECTID@appspot.gserviceaccount.com" \
  --role "organizations/$ORGID/roles/$ROLEID"

# TODO REMOVE
# create Cloud Task Queue. Routing is to default service
# (to change this, add  --routing-override=service:[SERVICE] )
#gcloud tasks queues describe "$QUEUE_ID" || gcloud tasks queues create "$QUEUE_ID" --log-sampling-ratio=1.0

#create PubSub topic
gcloud pubsub topics describe "$LOGS_TOPIC" ||
  gcloud pubsub topics create $LOGS_TOPIC --project="$PROJECTID" --quiet >/dev/null

#create PubSub topic for receiving commands from the /schedule handler that is triggered from cron
gcloud pubsub topics describe "$SCHEDULED_LABELING_TOPIC" ||
  gcloud pubsub topics create "$SCHEDULED_LABELING_TOPIC" --project="$PROJECTID" --quiet >/dev/null

log_filter=('protoPayload.methodName:(')
log_filter+=('"storage.buckets.create"' OR '"compute.instances.insert"' OR '"datasetservice.insert"')
log_filter+=('OR "tableservice.insert"' OR '"google.bigtable.admin.v2.BigtableInstanceAdmin.CreateInstance"')
log_filter+=('OR "cloudsql.instances.create"' OR '"v1.compute.disks.insert"' OR '"v1.compute.disks.createSnapshot"')
log_filter+=('OR "google.pubsub.v1.Subscriber.CreateSubscription"')
log_filter+=(')')

# create or update a sink at org level
if ! gcloud logging sinks describe --organization="$ORGID" "$LOGS_SINK_SUB" >&/dev/null; then
  gcloud logging sinks create "$LOGS_SINK_SUB" \
    pubsub.googleapis.com/projects/"$PROJECTID"/topics/"$LOGS_TOPIC" \
    --organization="$ORGID" --include-children \
    --log-filter="${log_filter[*]}" --quiet
else
  gcloud logging sinks update "$LOGS_SINK_SUB" \
    pubsub.googleapis.com/projects/"$PROJECTID"/topics/"$LOGS_TOPIC" \
    --organization="$ORGID" \
    --log-filter="${log_filter[*]}" --quiet
fi

# extract service account from sink configuration
svcaccount=$(gcloud logging sinks describe --organization="$ORGID" "$LOGS_SINK_SUB" | grep writerIdentity | awk '{print $2}')

# assign extracted service account to a topic with a publisher role
gcloud projects add-iam-policy-binding "$PROJECTID" \
  --member="$svcaccount" --role=roles/pubsub.publisher --quiet

# deploy the application
gcloud app deploy -q app.yaml queue.yaml
