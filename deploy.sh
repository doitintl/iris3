#!/usr/bin/env bash

# See usage (deploy.sh -h).
# Deploys Iris to Google App Engine, setting up Roles, Sinks, Topics, and Subscriptions as needed.

#set -x
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

START=$(date "+%s")

export LOGS_TOPIC=iris_logs_topic


deploy_proj=
deploy_org=
export CRON_ONLY=


while getopts 'cpoh' opt; do
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
      Usage deploy.sh PROJECT_ID
          Argument:
                  The project to which Iris will be deployed
          Options, to be given before project ID.
            If neither -p nor -o is given, the default behavior is used:
            to do both; this is equivalent to -p -o
            Flags:
                  -o: Deploy org-level elements like Log Sink
                  -p: Deploy project-level elements. This only works alone
                  without -o if  org-level elements were already deployed.
                  -c: Use only Cloud Scheduler cron to add labels;
                  If this is enabled, labels are not added on resource creation.
                  The default is without -c: Labels are added on both cron and resource creation.
                  (If, on the other hand, you want Iris to  *not* use Cloud Scheduler,
                  but only labeling on-creation, delete the schedule in cron.yaml.)
          Environment variable:
                  GAEVERSION (Optional) sets the Google App Engine Version.
EOF
    exit 1
    ;;
  esac
done

shift $(expr "$OPTIND" - 1 )

if [ "$#" -eq 0 ]; then
    echo Missing project id argument. Run with -h for usage.
    exit 1
fi

export PROJECT_ID=$1

pip3 install -r requirements.txt >/dev/null

if [[ "$deploy_org" != "true" ]] && [[ "$deploy_proj" != "true" ]]; then
  deploy_org=true
  deploy_proj=true
  echo >&2 "Default option: Deploy project and also org"
fi


gcloud projects describe "$PROJECT_ID" >/dev/null|| {
  echo "Project $PROJECT_ID not found"
  exit 1
}

echo "Project ID $PROJECT_ID"
gcloud config set project "$PROJECT_ID"


if [[ "$deploy_org" == "true" ]]; then
  ./scripts/_deploy-org.sh || exit 1
fi

if [[ "$deploy_proj" == "true" ]]; then
  ./scripts/_deploy-project.sh || exit 1
fi

FINISH=$(date "+%s")
ELAPSED_SEC=$((FINISH - START))
echo >&2 "Elapsed time for $(basename "$0") ${ELAPSED_SEC} s"
