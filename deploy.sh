#!/usr/bin/env bash

function error_exit
{
    echo "$1" 1>&2
    exit 1
}

if [[ $# -eq 0 ]] ; then
 echo Missing project id argument
 exit
fi

PROJECTID=`gcloud projects list | grep -iw "$1" | awk '{print $1}'`

if [ -z "$PROJECTID" ]; then
 echo Project $1 Not Found!
 exit
fi

#set the project context
echo Project ID $PROJECTID
gcloud config set project $PROJECTID

# Enable Cloud Resource Manager API if not enabled
if [ `gcloud services list --filter cloudresourcemanager.googleapis.com | wc -l` -eq 0 ]; then
  gcloud services enable cloudresourcemanager.googleapis.com
fi

# enable the pub/sub api, if not enabled already
if [ `gcloud services list --filter pubsub.googleapis.com | wc -l` -eq 0 ]; then
  gcloud services enable pubsub.googleapis.com
fi

# enable the compute api, if not enabled already
if [ `gcloud services list --filter compute.googleapis.com | wc -l` -eq 0 ]; then
  gcloud services enable compute.googleapis.com
fi

# enable the bigtable api, if not enabled already
if [ `gcloud services list --filter bigtable.googleapis.com | wc -l` -eq 0 ]; then
  gcloud services enable bigtable.googleapis.com
fi

# enable the cloudsql api, if not enabled already
if [ `gcloud services list --filter storage-component.googleapis.com | wc -l` -eq 0 ]; then
  gcloud services enable storage-component.googleapis.com
fi

# enable the cloud storage api, if not enabled already
if [ `gcloud services list --filter sql-component.googleapis.com | wc -l` -eq 0 ]; then
  gcloud services enable sql-component.googleapis.com
fi

# get organization id
ORGID=`gcloud organizations list |grep -v DISPLAY_NAME |awk '{print $2}'`

# create app engine app
gcloud app create --region=us-central

# create custom role to run iris
gcloud iam roles create iris --organization $ORGID --file roles.yaml

# assign default iris app engine service account with role on organization level
gcloud organizations add-iam-policy-binding $ORGID --member "serviceAccount:$PROJECTID@appspot.gserviceaccount.com" --role organizations/$ORGID/roles/iris

#create pub/sub topic
gcloud pubsub topics create iris_gce --project=$PROJECTID --quiet >/dev/null || error_exit "error creating pub/sub topic"

# create or update a sink at org level
gcloud logging sinks list --organization=$ORGID|grep iris_gce
RESULT=$?
if [ $RESULT -eq 1 ]; then
gcloud logging sinks create iris_gce  \
pubsub.googleapis.com/projects/$PROJECTID/topics/iris_gce --include-children \
--organization=$ORGID \
--log-filter="protoPayload.methodName:("storage.buckets.create"  OR "compute.instances.insert" OR "datasetservice.insert" OR "tableservice.insert" OR "google.bigtable.admin.v2.BigtableInstanceAdmin.CreateInstance" OR "cloudsql.instances.create" OR "v1.compute.disks.insert" OR "v1.compute.disks.createSnapshot")" --quiet >/dev/null || error_exit "error creating log sink"
else
gcloud logging sinks update iris_gce  \
pubsub.googleapis.com/projects/$PROJECTID/topics/iris_gce \
--organization=$ORGID \
--log-filter="protoPayload.methodName:("storage.buckets.create"  OR "compute.instances.insert" OR "datasetservice.insert" OR "tableservice.insert" OR "google.bigtable.admin.v2.BigtableInstanceAdmin.CreateInstance" OR "cloudsql.instances.create" OR "v1.compute.disks.insert" OR "v1.compute.disks.createSnapshot")" --quiet >/dev/null || error_exit "error creating log sink"
fi

# extract service account from sink configuration
svcaccount=`gcloud logging sinks describe --organization=$ORGID iris_gce|grep writerIdentity|awk '{print $2}'`

# assign extracted service account to a topic with a publisher role
gcloud projects add-iam-policy-binding $PROJECTID --member=$svcaccount --role='roles/pubsub.publisher' --quiet >/dev/null || error_exit "Error creating log sink"

# deploy the application
gcloud app deploy -q app.yaml cron.yaml queue.yaml
