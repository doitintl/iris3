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

echo Project ID $PROJECTID
gcloud config set project $PROJECTID

# Enable Cloud Resource Manager API if not enabled
if [ `gcloud services list --filter cloudresourcemanager.googleapis.com | wc -l` -eq 0 ]; then
  gcloud services enable cloudresourcemanager.googleapis.com
fi
ORGID=` gcloud organizations list      |awk '{print $2}'`
# create a sink at org level
gcloud logging sinks create iris_preemptible  \
pubsub.googleapis.com/projects/$PROJECTID/topics/iris_preemptible --include-children \
--organization=$ORGID --log-filter="resource.type="gce_instance"
protoPayload.methodName="v1.compute.instances.insert""
gcloud app deploy -q app.yaml cron.yaml queue.yaml