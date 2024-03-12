# Creates a project. Useful for testing. Creates the App Engine default service as well -- a prereq for Iris.
set -u
#set -x
set -e

gcloud projects create $PROJ --folder=$FOLDER # or else   --organization=$ORG
gcloud billing projects link $PROJ --billing-account $BILL
pushd helloworld_appengine ||exit
gcloud app create --region us-west4 --project $PROJ
gcloud app deploy -q --project $PROJ
popd ||exit
