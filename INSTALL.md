# How to Install

(For the main documentation, see [README](./README.md).)

## Before deploying

### In which Project 

* You can deploy Iris in any one project within your Google Cloud organization, but we recommend using a [new project](https://cloud.google.com/resource-manager/docs/creating-managing-projects#creating_a_project) just for this.
* The script will deploy Iris (an App Engine service) into this project. That does not mean that Iris is focused on labeling this project. (See [README](./README.md).)

### Needed roles for deployment
#### Organization-level roles

* Here are the required organization-level roles for you, the deployer, to allow the deploy script to set up roles and log sink. (Note that *Organization Owner* is not enough).
    * *Organization Role Administrator* so the deployment script can create a custom IAM role for Iris that allows it to get and set labels.
    * *Security Admin* so the deployment script can grant the needed role bindings, e.g., to the App Engine service account.
    * *Logs Configuration Writer* so the deployment script can create an organization log sink that sends logs to
      PubSub.

#### Project-level roles
* The required project-level roles: *Project Owner* or *Project Editor* on the project where Iris is deployed, so that the deployment script can 
  * create role bindings, topics and subscriptions
  * deploy App Engine. 
  * `actAs` the serivice account `iris-msg-sender` for deploying it to allow JWT auth.

* You cannot replace  *Project Owner* or *Project Editor* with fine-granted "predefined roles" are not possible because deploying Cloud Scheduler cron requires at least Editor or Owner, per GCP docs.

## Deployment

* Get the code with `git clone https://github.com/doitintl/iris3.git`
* Have Python 3.9+ as your default `python3`.
* Make sure you have these tools
    * `envsubst`
    * `jq`
    * The command-line `pip3`
    * `gcloud`. Make sure it is logged-in using an account with the [above-mentioned](#before-deploying) roles.
* Set up the configuration
    * Copy `config.yaml.original` to `config.yaml`.
    * Optionally configure by editing the config file. ([See more documentation below](#configuration).)
* As always with App Engine, a default service must exist before any other exists. So if you are working with a new project:
  * Initialize App Engine with `gcloud app create [--region=REGION]`
  * Deploy a simple "Hello World" default App Engine service. (See `create_project.sh` for an example (not a runnable part of the installation) of creating a project and creating the default App Engine service.)
* Now, run `./deploy.sh <PROJECT_ID> `
  * For documentation on usage of command-line options, run `deploy.sh -h` 
* Choosing when the labeling occurs
  * By default, labeling occurs on resource-creation, and also using Cloud Scheduler ("cron"). 
    * Each of these works on certain resource types and not others (see [Supported Google Cloud resources](README#Supported Google Cloud resources) in the main README), depending on configuration (`config.yaml`).
  * Use `-c` switch on `deploy.sh` to label using Cloud Scheduler only.
  * Use `-e` switch on `deploy.sh` to label on-event only.
  * If you use **both** `-c` and `-e` or **neither**, then both types of labeling occur.
  * To label all resources, including those not configured for being labeled on Cloud Scheduler, see section "[Labeling existing resources](README.md#labeling-existing-resources)" in the main README. 


# Configuration

* Iris' config file is `config*.yaml`.
    * All values are optional.
    * `config.yaml.orig` has detailed documentation of the fields.
* Alternatively, you can have `config-test.yaml`. It takes priority if both it and `config-test.yaml` are present.
* `app.yaml` lets you configure App Engine, for example, to set a maximum number of instances. See App Engine documentation.
* Editing `cron_full.yaml` lets you optionally change the timing for the Cloud Scheduler scheduled labelings, e.g. to do it more frequently. See Google App Engine documentation.

# Uninstalling

* Run script `uninstall.sh`
* Use `uninstall.sh -h` for help.

# Architecture
Please see [README_architecture](README_architecture.md)

# Development and Testing
Please see [HACKING](./HACKING.md)
 