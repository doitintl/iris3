# Iris

In Greek mythology, Iris(Ἶρις) is the personification of the rainbow and messenger of the gods. She was the handmaiden to Hera.
![Iris](./iris.jpg "Iris") 
# Blog post

See
the [post that presents Iris](https://blog.doit-intl.com/iris-3-automatic-labeling-for-cost-control-7451b480ee13?source=friends_link&sk=b934039e5dc35c9d5e377b6a15fb6381).

# What Iris does for you

Iris automatically assigns labels to Google Cloud Platform resources for easier analysis, particularly of cost.

Resources of all supported types in all or some of the projects in the GCP organization will get automatically-generated labels with keys like `iris_zone` (the prefix is configurable), and a value copied from the resource. For example, a Google Compute Engine instance would get labels like
`[iris_name:nginx]`, `[iris_region:us-central1]` and `[iris_zone:us-central1-a]`. This behavior can be configured in various ways; see below.

## Note: Organization focus

Note that Iris is designed to serve the organization. 
* It is designed to label all projects in the organization (though you can configure that).
* The organization focus was chosen because labels are used for billing analysis which is typically done on the organization level (even though projects can in fact be associated arbitrarily with billing accounts). 

## Iris doesn't add new information

Iris does not *add* information, only *copy* values that already exist. For example, it can label a VM instance with its zone; but it cannot add a "business unit" label because it does not know a resource's business unit. For that, you should label all resources when creating them, e.g., in your Terraform scripts. (Indeed, iris can be made extraneous in this way.)

## Labeling existing resources when you deploy Iris

If you want to label the resources -- virtual machines, PubSub topics etc. -- that *already exist* when you deploy Iris, see section "[Labeling existing resources](#labeling-existing-resources)" below.

# Open source

Iris is open-source;it is not an official DoiT product. Feel free to send Pull Requests with  new functionality and add new types of labels. See the `TODO.md` file and Github
issues for features and fixes you might do.

# When Iris adds labels

## On resource creation

Iris labels newly-created resources by listening to Google Cloud Operations   Logs. You can disable this: See ["Deploy"](#deployment) or run `deploy.sh -h`.

## On schedule

Iris labels resources periodically on a Cloud Scheduler "cron" job. By default, only some types of resources are labeled on  these Cloud Scheduler runs, while most types are not labeled on schedule,  , to save the costs of relabeling with the same label every day.

You can change that in configuration. Set `label_all_on_cron` to `True` in the configuration file.

You can also  disable the scheduled labeling. See Deployment below or run `./deploy.sh -h`

## Labeling existing resources

* When you first use Iris, you may want to label all existing resources. Iris does not do this by default.
* You have two choices:
  * Set configuration `label_all_on_cron: true` before deploying. Then, on the next daily Cloud Scheduler run, all resources will be labeled. However, this will increase cost, since all resources will be rescanned every day.
  * Alternatively, after deploying publish a PubSub message (the content doesn't matter) to `iris_label_all_topic`, for example with `gcloud pubsub topics publish iris_label_all_topic --message=does_not_matter --project $PROJECT_ID` and a full labeling will be triggered.

# Supported Google Cloud resources

Right now, there are plugins for the following types of resources.

To learn from the code what resources and keys are added, search for functions whose
names start `_gcp_`. The part of the function name after `_gcp_` is used for the label key.

* Compute Engine Instances (Labels name, zone, region, instance type)
    * Including preemptible instances and instances created by Managed Instance Groups.
    * Including instances used as GKE Nodes
* Compute Engine Disks (Labels name, zone, region)
    * Disks are labeld on creation and on schedule.
    * But disks created along with an Instance are not labeled on creation. They are labeled with the Cloud Scheduler cron job.
    * The label indicating whether a disk is attached will change, if the state changed, on the scheduled labeling.
* Compute Engine Snapshots (Labels name, zone, region)
* BigQuery Datasets (Labels name, zone, region)
* BigQuery Tables (Labels name, zone, region)
* PubSub Subscriptions (Labels name)
* PubSub Topics (Labels name, zone)
* CloudSQL (Labels name, zone, region)
    * These receive a label only with Cloud Scheduler, not on creation.
* Cloud Storage buckets (Labels name, location)
* In addition to these, any labels on a project may be copied into the resourcs that are in the project, if you have enabled this in  the
  configuration file.

# Installation/Deployment

## Before deploying

### In which Project 

* You can deploy Iris in any project within your Google Cloud organization, but we recommend using a
  [new project](https://cloud.google.com/resource-manager/docs/creating-managing-projects#creating_a_project).

### Needed roles for deployment
#### Organization-level roles

* Here are the required organization-level roles for you, the deployer, to allow the deploy script to set up roles and  log sink. (Note that *Organization Owner* is not enough).
    * *Organization Role Administrator*  so the deployment script can create a custom IAM role for Iris that allows it to  get and set labels.
    * *Security Admin* so the deployment script can grant the needed role bindings, e.g., to the App Engine service account.
    * *Logs Configuration Writer* so the deployment script can create an organization log sink that sends logs to
      PubSub.

#### Project-level roles
* The required project-level roles: *Project Owner* or *Project Editor* on the project where Iris is deployed, so that the deployment script can 
  * create role bindings, topics and subscriptions
  * deploy App Engine. 
  * `actAs` the serivice account `iris-msg-sender` for deploying it to allow JWT auth.

* Fine-granted "predefined roles" are not possible because deploying Cloud Scheduler cron requires at least Editor or Owner, per GCP docs.

 

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

* Now, run `./deploy.sh <PROJECT_ID> `.
  * For documentation on usage of command-line options, run `deploy.sh -h` 
 
* Choosing when the labeling occurs
  * By default, labeling occurs on resource-creation, and also using Cloud Scheduler ("cron"). Each of these types works on certain resource types and not others (see [Supported Google Cloud Labels](#Supported Google Cloud Labels) above), depending on configuration (`config.yaml`).
  * Use `-c` switch on `deploy.sh` to label using Cloud Scheduler only.
  * Use `-e` switch on `deploy.sh` to label on-event only.
  * If you use **both** `-c` and `-e` or **neither**, both types of labeling occur.



# Configuration

* Iris' config file is `config*.yaml`.
    * All values are optional.
    * `config.yaml.orig` has detailed documentation of the fields.
* `config.yaml` is read as the production configuration file
* Alternatively, you  can   have  `config-test.yaml`. It takes priority if both it and `config-test.yaml` are present.

* `app.yaml` lets you configure App Engine, for example, to set a maximum number of instances. See App Engine documentation.
* Editing `cron_full.yaml` lets you optionally change the timing for the Cloud Scheduler scheduled labelings, e.g. to do it  more frequently. See Google App Engine documentation.

# Uninstalling

* Run script `uninstall.sh`
* * See a comment in `uninstall.sh` that describes what elements are uninstalled. The default is to uninstall everything, both the org-level components and the project-level components.
* Run `uninstall.sh -h` for help.
* A full uninstall will also delete the custom role. This will then block you from re-deploying  unless you first either undelete the custom role or else give a new custom-role name at the top of `custom-iris-role.yaml`.

# Architecture

* Iris runs in Google App Engine Standard Environment (Python 3).
* Organization-level and project-level elements
  * First, note that Iris is an organization-level application.
  * A single instance of Iris in one project labels all projects in an org (unless you limit it by configuration). 
  * Iris has architecture elements which are deployed to both the org and the project.
  * If you want a person with all permissions to deploy the org-level elements and a person without org-level permissions to redeploy only the project-level elements (e.g. when you change configuration), you can do this with flags on the script. Run `deploy.sh -h`.
* The Cloud Scheduler "cron" job triggers Iris at configured intervals. See `cron_full.yaml` for config. The GCP Console view for this is in a  separate App Engine tab in the Cloud Scheduler view.
* For newly created resources, a Log Sink on the organization level sends all logs for resource creation to a PubSub  topic.
    * The Log Sink is filtered to include only supported resource types
    * If you edit the configuration file so that  only specific projects are to be labeled, the Log Sink only captures these.
* PubSub topics:
    * One topic receives the resource-creation logs from the Log Sink
    * Another topic receives messages sent by the `/schedule` Cloud Scheduler handler in `main.py`. (The `/schedule` path is triggered by the Cloud Scheduler). This then sends out messages, where each one triggers the labeling of a given resource tyope in a given project.
    * Another topic is a dead-letter topic.
* PubSub subscriptions
    * There is one for each topic: These direct the messages to `/label_one` and `/do_label` in `main.py`, respectively.
    * For security, these two PubSub subscriptions [use JWT auth](https://cloud.google.com/pubsub/docs/authenticate-push-subscriptions), where the JWT token is verified in the Iris webapp.
    * A dead-letter subscription. This is a pull subscription. By default, it just accumulates the messages. You can use it to see statistics, or you can pull messages from it.

# Development and Testing

Please see [README_for_dev_and_testing](./README_for_dev_and_testing.md)
 
