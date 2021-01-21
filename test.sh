#!/bin/zsh


set -u
set -e

START=$(date "+%s")

if [[ $# -lt 2 ]]; then
  echo "Missing project ID arguments: Need deployment project and project-under-test"
  exit
fi
depl_proj=$1
test_proj=$2
declare -a projects
projects=("$depl_proj" "$test_proj")
for  p in "${projects[@]}" ; do
  gcloud projects describe "$p" || {
    echo "Project $p not found"
    exit 1
  }
done

REPLACE IRIS PREFIX in config.yaml, then restore
./deploy.sh $depl_proj

rand=$(base64 < /dev/urandom | tr -d 'O0Il1+/' | head -c 4| awk '{print tolower($0)}')



gcloud config set project "$test_proj"

gcloud compute instances create "instance${rand}" --project "$test_proj"
# The name of the disk was created as the same as the instance that holds it.
gcloud compute disks snapshot "instance${rand}" --snapshot-names "snapshot${rand}" --project $test_proj
gcloud pubsub topics create "topic${rand}" --project "$test_proj"
gcloud pubsub subscriptions  create "subscription${rand}" --topic "topic${rand}" --project "$test_proj"
bq mk --dataset "${test_proj}:dataset${rand}"
bq mk --table "${test_proj}:dataset${rand}.table${rand}"
gsutil mb -p $test_proj "gs://bucket${rand}"

#TODO check each object for labels


gcloud compute instances delete "instance${rand}" --project "$test_proj"
gcloud compute snapshot delete "snapshot${rand}" --project $test_proj
gcloud pubsub topics delete "topic${rand}" --project "$test_proj"
gcloud pubsub subscriptions delete "subscription${rand}" --project "$test_proj"
bq rm --dataset "${test_proj}:dataset${rand}"
bq rm --table "${test_proj}:dataset${rand}.table${rand}"
gsutil rm -r "gs://bucket${rand}"


FINISH=$(date "+%s")
ELAPSED_SEC=$((FINISH - START))
echo "Elapsed time ${ELAPSED_SEC} s"
