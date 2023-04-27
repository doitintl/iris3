#!/usr/bin/env bash
#
# Deploys Iris to Google App Engine, setting up Roles, Sinks, Topics, and Subscriptions as needed.
# Usage
# - Pass the project as the first command line argument.
# - Options -p -o -c as documented in usage (try -h)
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
python3 ./util/check_python_version.py

pip3 install -r requirements.txt

START=$(date "+%s")

export LOGS_TOPIC=iris_logs_topic

if [[ $# -eq 0 ]]; then
  echo Missing project id argument. Run with --help switch for usage.
  exit
fi

export PROJECT_ID=$1

shift
deploy_proj=
deploy_org=
export CRON_ONLY=
while getopts 'cpo' opt; do
  case $opt in
  c)
    export CRON_ONLY=true
    ;;
  p)
    deploy_proj=true
    ;;
  o)
    deploy_org=true
    ;;
  *)
    cat <<EOF
      Usage deploy.sh PROJECT_ID [-c]
          Argument:
                  The project to which Iris 3 will be deployed
          Options, to be given at end of line, after project ID.
            If neither -p nor -o is given, this is treated as the default, -p -o (i.e., do both):
                  -p: Deploy Iris (to the project given by the arg)
                  -o: Set up org-level elements like Log Sink
                  -c: Use only Cloud Scheduler cron to add labels; do not add labels on resource creation.
                  If you are changing to be Cloud-Scheduler-only with -c or not Cloud_Scheduler-only
                  without -c, be sure to run both org and project deployments.
                  (To *not at all* use Cloud Scheduler, delete the schedule in `cron.yaml`.)
          Environment variable:
                  GAEVERSION (Optional) sets the Google App Engine Version.
EOF
    exit 1
    ;;
  esac
done

if [[ "$deploy_org" != "true" ]] && [[ "$deploy_proj" != "true" ]]; then
  deploy_org=true
  deploy_proj=true
  echo >&2 "Default option: Deploy project and also org"
fi


gcloud projects describe "$PROJECT_ID" || {
  echo "Project $PROJECT_ID not found"
  exit 1
}

echo "Project ID $PROJECT_ID"
gcloud config set project "$PROJECT_ID"

if [[ "$deploy_org" == "true" ]]; then
  ./scripts/_deploy-org.sh
fi

if [[ "$deploy_proj" == "true" ]]; then
  ./scripts/_deploy-project.sh
fi

FINISH=$(date "+%s")
ELAPSED_SEC=$((FINISH - START))
echo >&2 "Elapsed time for $(basename "$0") ${ELAPSED_SEC} s"
