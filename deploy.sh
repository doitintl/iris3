#!/usr/bin/env bash

set -ex

ROLEID=iris
TOPIC=iris_gce
SINK=iris_gce

if [[ $# -eq 0 ]] ; then
 echo Missing project id argument
 exit
fi

PROJECTID=$(gcloud projects list | grep -iw "$1" | awk '{print $1}')

if [ -z "$PROJECTID" ]; then
	echo "Project $1 Not Found!"
	exit 1
fi

#set the project context
echo "Project ID $PROJECTID"
gcloud config set project "$PROJECTID"

declare -A enabled_services
while read -r svc _ ; do
	enabled_services["$svc"]=yes
done < <(gcloud services list |tail -n +2)

required_svcs=(
	cloudresourcemanager.googleapis.com
	pubsub.googleapis.com
	compute.googleapis.com
	bigtable.googleapis.com
	storage-component.googleapis.com
	sql-component.googleapis.com
)

# Enable services if they are not
for svc in "${required_svcs[@]}"; do
	[[ "${enabled_services["$svc"]}" == "yes" ]] || gcloud services enable "$svc"
done

# get organization id
ORGID=$(curl -X POST -H "Authorization: Bearer \"$(gcloud auth print-access-token)\"" \
   -H "Content-Type: application/json; charset=utf-8"  \
   https://cloudresourcemanager.googleapis.com/v1/projects/"${PROJECTID}":getAncestry |  grep -A 1 organization \
    | tail -n 1 | tr -d ' ' | cut -d'"' -f4)

# create app engine app
gcloud app describe >&/dev/null || gcloud app create --region=us-central

# create custom role to run iris
gcloud iam roles describe "$ROLEID" --organization "$ORGID" || \
	gcloud iam roles create "$ROLEID" --organization "$ORGID" --file roles.yaml

# assign default iris app engine service account with role on organization level
gcloud organizations add-iam-policy-binding "$ORGID" \
	--member "serviceAccount:$PROJECTID@appspot.gserviceaccount.com" \
	--role "organizations/$ORGID/roles/$ROLEID"

#create pub/sub topic
gcloud pubsub topics describe "$TOPIC" || \
	gcloud pubsub topics create iris_gce --project="$PROJECTID" --quiet >/dev/null

log_filter=('protoPayload.methodName:(')
log_filter+=('"storage.buckets.create"' OR '"compute.instances.insert"' OR '"datasetservice.insert"')
log_filter+=('OR "tableservice.insert"' OR '"google.bigtable.admin.v2.BigtableInstanceAdmin.CreateInstance"')
log_filter+=('OR "cloudsql.instances.create"' OR '"v1.compute.disks.insert"' OR '"v1.compute.disks.createSnapshot"')
log_filter+=(')')

# create or update a sink at org level
if ! gcloud logging sinks describe --organization="$ORGID" "$SINK" >&/dev/null; then
	gcloud logging sinks create "$SINK" \
		pubsub.googleapis.com/projects/"$PROJECTID"/topics/"$TOPIC" \
		--organization="$ORGID" --include-children \
		--log-filter="${log_filter[*]}" --quiet
else
	gcloud logging sinks update "$SINK" \
		pubsub.googleapis.com/projects/"$PROJECTID"/topics/"$TOPIC" \
		--organization="$ORGID" \
		--log-filter="${log_filter[*]}" --quiet
fi

# extract service account from sink configuration
svcaccount=$(gcloud logging sinks describe --organization="$ORGID" "$SINK"|grep writerIdentity|awk '{print $2}')

# assign extracted service account to a topic with a publisher role
gcloud projects add-iam-policy-binding "$PROJECTID" \
	--member="$svcaccount" --role=roles/pubsub.publisher --quiet

# deploy the application
gcloud app deploy -q app.yaml cron.yaml queue.yaml
