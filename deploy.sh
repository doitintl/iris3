#!/usr/bin/env bash

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

ORGID=`gcloud organizations list |grep -v DISPLAY_NAME |awk '{print $2}'`

#create pub/sub topic
gcloud pubsub topics create iris_gce --project=$PROJECTID --quiet >/dev/null || error_exit "error creating pub/sub topic"

# create a sink at org level
gcloud logging sinks create iris_gce  \
pubsub.googleapis.com/projects/$PROJECTID/topics/iris_gce --include-children \
--organization=$ORGID \
--log-filter="resource.type="gce_instance" protoPayload.methodName="v1.compute.instances.insert"" --quiet >/dev/null || error_exit "error creating log sink"

# extract service account from sink configuration
svcaccount=`gcloud logging sinks describe iris_gce|grep writerIdentity|awk '{print $2}'`

# assign extracted service account to a topic with a publisher role
gcloud projects add-iam-policy-binding $PROJECTID --member=$svcaccount --role='roles/pubsub.publisher' --quiet >/dev/null || error_exit "Error creating log sink"

# deploy the application
gcloud app deploy -q app.yaml cron.yaml queue.yaml
