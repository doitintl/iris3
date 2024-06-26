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
export LABEL_ON_CRON=
export LABEL_ON_CREATION_EVENT=

while getopts 'cepoh' opt; do
  case $opt in
  c)
    export LABEL_ON_CRON=true
    ;;
  e)
    export LABEL_ON_CREATION_EVENT=true
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
          Flags: Advanced options. Not to be used in most cases.
                  A. Labeling only on-creation or on-schedule:
                  -c: Label on Cloud Scheduler cron only
                  -e: Label on-creation-event only
                  The default, if neither -c or -e are given, is to enable both; equivalent to -c -e

                  B. Project/Org level elements with -p or -o. If neither -p nor -o is given,
                  the default behavior is to do both; equivalent to -p -o.
                  Note that Iris is always focused on labeling in an org. See README. These flags
                  are just about limiting the components that are installed when some already are installed.
                  -o: Deploy org-level elements like Log Sink
                  -p: Deploy project-level elements.  Org-level elements are a pre-requisite.
                  This is useful for redeploying to the same project, e.g., to change config.
                  If you want to deploy to a *different* project, then you have to deploy the
                  org-level elements.

          Environment variable:
                  IRIS_CUSTOM_ROLE (Optional, default is iris3) An identifier for the Iris custom role,
                  which will be created as needed.
                  SKIP_ADDING_IAM_BINDINGS: If "true", then IAM bindings will not be added
                  on the org or project level. This is useful when rerunning many times for a test,
                  since quotas/limits kick in.

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

pip3 install -r requirements.txt > /dev/null

# If both -c and -e are not given, then actually act as if both are there.
if [[ "$LABEL_ON_CRON" != "true" ]] && [[ "$LABEL_ON_CREATION_EVENT" != "true" ]]; then
  export LABEL_ON_CRON=true
  export LABEL_ON_CREATION_EVENT=true
fi


# If both -p and -o or neither is given, we do the default behavior of deploying both types of components
if [[ "$deploy_org" != "true" ]] && [[ "$deploy_proj" != "true" ]]; then
  deploy_org=true
  deploy_proj=true
fi

gcloud services enable cloudresourcemanager.googleapis.com --project $PROJECT_ID > /dev/null ||true

gcloud projects describe "$PROJECT_ID" >/dev/null || {
  echo "Project $PROJECT_ID not found"
  exit 1
}

gcloud config set project "$PROJECT_ID" > /dev/null

export LOG_SINK=iris_log

# Get organization id for this project
ORGID=$(gcloud projects get-ancestors "$PROJECT_ID" --format='value(TYPE,ID)' | awk '/org/ {print $2}')
export ORGID

if [[ "$deploy_org" == "true" ]]; then
  ./scripts/_deploy-org.sh || exit 1
fi

if [[ "$deploy_proj" == "true" ]]; then
  ./scripts/_deploy-project.sh || exit 1
fi

FINISH=$(date "+%s")
ELAPSED_SEC=$((FINISH - START))
echo >&2 "Elapsed time for $(basename "$0") ${ELAPSED_SEC} s"
