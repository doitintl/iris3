# Iris

In Greek mythology, Iris (/ˈaɪrɪs/; Greek: Ἶρις) is the personification of the rainbow and messenger of the gods. She
was the handmaiden to Hera.

# Blog post

See
the [post that presents Iris](https://blog.doit-intl.com/iris-3-automatic-labeling-for-cost-control-7451b480ee13?source=friends_link&sk=b934039e5dc35c9d5e377b6a15fb6381).

# What Iris does for you

Iris automatically assigns labels to Google Cloud Platform resources for manageability and easier billing reporting.

All supported resources in all projects in the GCP organization will get automatically-generated labels.

with keys like `iris_zone` (the
prefix is configurable), and a value copied from the resouce.
For example, a Google Compute Engine instance would get labels like
`[iris_name:nginx]`, `[iris_region:us-central1]` and `[iris_zone:us-central1-a]`. This behavior can be configured in various ways; see below.

## Note: Organization focus
Note that Iris is designed to serve the org. It is not designed around serving a single project, but you can do that by configuring the project-filter to only label one project.

## Iris doesn't add information
Iris does not *add* information, only *copy* values that already exist. For example, it can label a VM instance with its zone, since this information is known; but it cannot add a "business unit" label because it does not know what business
unit a resource should be attributed to. For that, you should label all resources when creating them, e.g., in your Terraform scripts.

## Iris doesn't by default label all existing resources.

To do it, see section [Labeling existing resources](#Labeling existing resources) below.

# Open source
Iris is open-source: Feel free to add functionality and add new types of labels. See the `TODO.md` file and Github issues for features and fixes you might do.

# When Iris adds labels

Iris adds labels:
## On resource creation
It knows about new resources to label by listening to Google Cloud Operations (Stackdriver) Logs. You can disable this, see ["Deploy"](#deployment).
## On schedule
It can run on a Cloud Scheduler cron job that the deployer sets up for you. By default, only some types of resources are labeled on Cloud Scheduler runs. Most do not receive labels on Scheduler, to save the costs of relabeling with the same label every day.

However,  this can be configured so that all resources are labeled. See `label_all_on_cron` below.

Or you can disable the schedule labeling.

## Labeling existing resources

* When you first use Iris, you may want to label all existing resources. This is not Iris' preferred flow for adding labels, but you can do it.
* To do this, deploy it with `label_all_on_cron: True` and wait for the next scheduled run, or manually trigger a run.
* Thenּ, you may want to then redeploy Iris with `label_all_on_cron: False` to avoid the  resource consumption of relabeling all resources with the same label every day forever.

# Supported Google Cloud resources

Right now, there are plugins for the following types of resources.

To learn from the code what resources and keys are added, search for `def _gcp_<LABEL_NAME>)`, i.e., functions whose
names start `_gcp_`.
The part of the function name after `_gcp_` is used for the label key.

* Compute Engine Instances (Labels name, zone, region, instance type)
    * Including preemptible instances or instances created by Managed Instance Groups.
    * Including instances used as GKE Nodes
* Compute Engine Disks (Labels name, zone, region)
    * Disks created with an Instance are not labeled on-creation. They are labeled with the Cloud Scheduler cron job.
    * The label indicating whether a disk is attached will change, if the state changed, on the cron job, not on-event.
* Compute Engine Snapshots (Labels name, zone, region)
* BigQuery Datasets (Labels name, zone, region)
* BigQuery Tables (Labels name, zone, region)
* PubSub Subscriptions (Labels name)
* PubSub Topics (Labels name, zone)
* CloudSQL (Labels name, zone, region)
    * These receive a label only on the Cloud Scheduler cron job, not on creation.
* Cloud Storage buckets (Labels name, location)
* In addition to these, project labels may be copied into each resource, if you have configured that in the
  configuration file.

# Installation/Deployment

## Before deploying

### Org and IAM

* You can deploy Iris in any project within your Google Cloud organization, but we recommend using a
  [new project](https://cloud.google.com/resource-manager/docs/creating-managing-projects#creating_a_project).

* You need to have certain permissions to run the deployment script to deploy Iris on the org level--the deploy script sets up  roles and log sink. You will need to have these roles on the *organization* where Iris is deployed. You do not need to have these roles if you are doing further re-deployments of new versions of Iris on the project level (where you use the `-p` switch on `deploy.sh`.
    * *Organization Role Administrator*  so the deployment script can create a custom IAM role for Iris that allows to get and set labels.
    * (Note that *Organization Owner* is not enough).
    * *Security Admin* **or** *Organization Administrator* so the deployment script can allow the Iris app engine service account to have the needed permissions.
    * *Logs Configuration Writer* so the deployment script can  create an organization log sink that sends logs to PubSub.

* You need to have certain permissions to run the deployment script to deploy Iris on the project level.
  * One option: You can have *Project Owner* on the project where Iris is deployed
  * Another option: You can have these roles.
      * *Project IAM Admin* to let the deployment script set up the bindings.
      * *App Engine Admin* to let the deployment script deploy to App Engine.
      * *Pub/Sub Admin* to let the deployment script create topics and subscriptions.

### App Engine Defaults
#### Default Service
App Engine requires a "default service" to exist (even though Iris runs as the `iris3` service).

If your project does not have a default service, just deploy some trivial=Hello World app as the default service. (Having this service  costs nothing.) Try [this](https://github.com/doitintl/QuickQuickstarts/tree/main/appengine_standard ) open-source that I wrote to do that as easily as possible; or else step through [this tutorial](https://cloud.google.com/appengine/docs/standard/python3/building-app) from Google.

#### Regions
Iris works  in the AppEngine default region `us-central1` (`uc`) which is the default for AppEngine

Note also that AppEngine does not let you change a region once it has been set to a non-default.

Iris has not been tested in other regions, but if you want to try it, edit `GAE_REGION_ABBREV` in `_deploy_project.sh` and let me know how it goes.


## Deployment

* Get the code with `git clone https://github.com/doitintl/iris3.git`
* Have Python 3.9+ as your default `python3`.
* Makes sure you have these tools
  * `envsubst`
  * `jq`
  * The command-line `pip3`
  *  `gcloud`. Make sure it is logged-in  using an account with the [above-mentioned](#before-deploying) roles.
* Set up the configuration
  * Copy `config.yaml.original` to `config.yaml`.
  * Optionally configure by editing the configuration files ([See more documentation below](#configuration).)
* If you choose a project with `dev`, `qa`, `playground`, or `test` in its ID, note that there is a circuit-breaker will block scheduled labeling under these conditions. This is meant to protect from accidentally flooding thousands of projects  with test-labels.
  * The conditions:
    * More than 3 projects are to be labeled.
    * Iris is running in the cloud in App Engine (rather than in your dev machine)
    * if you use `config-dev.yaml` or `config-test.yaml`
  * To disable the circuit-breaking, edit `test_or_dev_project_markers` in the configuration file.  
* Now, run `./deploy.sh <PROJECT_ID> `.
   * The above is the default.
   * There are also command-line options.
   * Run `deploy.sh -h` for documentation.
* When you redeploy different versions of Iris code on top of old ones:
    * If new plugins were added or some removed, the log sink *will* be updated to reflect this.
    * If the parameters for subscriptions or topics were changed in a new version of the Iris code, the subscriptions or  topics will *not* be updated. You would have to delete them first.
* If you are changing the value of "Cloud-Scheduler-only" with `-c` (or the opposite, without `-c`) on a previous deployment), be sure to run both org and project deployments, not just project deployment, since this involves the org-level sink.         
* Run  `deploy.sh -h` for configuring Iris
  * to add labels only with  Cloud Scheduler (and not on-creation
  * or without the Scheduler at all
  * or with both Scheduler and on-creation. (This is the default.)

# Configuration

* Iris'  config file is `config*.yaml`.  All values are optional.
* You can also have  `config-test.yaml`, or `config-dev.yaml`
      * They take priority in this order:
        * If `config-dev.yaml` is present, that is used;
        * if not, and `config-test.yaml` is present, that is used;
         * otherwise `config.yaml` is used.
      * Local vs App Engine
        * `config-dev.yaml` is not uploaded to App Engine and so is ignored there.
        * `config-test.yaml` and `config.yaml` are available for use in App Engine.


* `app.yaml` lets you configure App Engine, for example to set a maximum number of instances. See App Engine
  documentation.
* `cron.yaml` lets you optionally change the timing for the Cloud Scheduler scheduled labelings. See App Engine
  documentation.

# Uninstalling
* See script `uninstall.sh`
* Run `uninstall.sh -h` for help.
* A full uninstall will also delete the custom role.  You will then not be able to re-deploy unless you first either undelete the custom role or else give a new custom-role name at the top of `custom-iris-role.yaml`.,
# Architecture

* Iris runs in Google App Engine Standard Environment (Python 3).
* The Cloud Scheduler "cron" job triggers Iris at configured intervals. (See `cron.yaml`)
* For newly created resources, a Log Sink on the organization level sends all logs for resource-creation to a PubSub
  topic.
    * The Log Sink is filtered to include only supported resource types
    * If you edit the configuration file to support only specific projects, the Log Sink only captures these.
* PubSub topics:
    * One topic receives the resource-creation logs from the Log Sink
    * Another topic receives messages sent by the `/schedule` Cloud Scheduler handler in `main.py`. (The `/schedule` path is triggered by  the Cloud Scheduler.
        * Such messages are an instruction to call `do_label` for each combination of (project, resource-type).
    * Another topic is a dead-letter topic
* PubSub subscriptions
    * There is one for each topic: These direct the messages to `/label_one` and `/do_label` in `main.py`, respectively
    * A dead-letter subscription. This is a pull subscription. By default, it just accumulates the messages. You can use
      it to see statistics, or you can pull messages from it.

# Local Development

## Development tools

* Prerequisites for developing and building.
    * See [Installation](#installation)
    * Also, for development, set up a virtual env and run `pip3 install -r requirements.txt`
* Run the server locally
    * Run `main.py` as an ordinary Flask application as follows:
        * To use the command-line,
          use `export FLASK_ENV=development;export FLASK_RUN_PORT=8000;export FLASK_DEBUG=1;FLASK_APP=main.py python -m flask run`
        * In an interactive development environment, run `main.py`, first setting these environment variables.
* For hands-on debugging
    * Set the projects you want to use in  `config-dev.yaml`
    * Use `test_do_label` and `test_label_one` and `test_schedule` to trigger against your localhost dev-server, to
      label actual Cloud resources that you pre-deploy.
        * See the `test_...` files for instructions.

## Adding new kinds of labels.

Iris adds about twenty kinds of labels. More can be added, but don't add too many. Billing analytics work best when not
swamped by excess labels. This is why GCP doesn't simply add these labels, and why Iris does not implement all possible
labeling, say by automatically copying all fields from each resource into labels.

## Developing new labels for an existing resource type

To add a new label key to an existing resource type, add `_gcp_<LABEL_NAME>` methods (like `_gcp_zone()`) in the
relevant file in `/plugins`, following the example of the existing ones. Labels will be added with a key from the
function name (`zone` in that example), and a value returned by the function
(in our example, the zone identifier).

For example, you might want to add a label identifying the creator of a resource, or add the name of the topic to its
subscriptions.

## Supporting new resource types

Iris is easily extensible with plugins, to support labeling of other GCP resources. Use existing files in `/plugins` as
examples.

1. Create a Python file in the `/plugins` directory, holding a subclass of `Plugin`.

   a. The filename and class name take the form: `cloudsql.py` and `Cloudsql`. That's lowercase and Titlecase. (Only the  first character is capitalized, even in multiword names.) The two names should be the same except for case.

   b. Implement abstract methods from the `Plugin` class.

   c. Add `_gcp_<LABEL_NAME>` methods (like `_gcp_zone()`). Labels will be added with a key from the function
   name (`zone` in that example), and a value returned by the function
   (in our example, the zone identifier).

   d. For resources that cannot be labeled on creation (like CloudSQL, which takes too long to initialize), you should
   override `is_labeled_on_creation()` and return `False`  (though if you don't, the only bad-side effect will be errors
   in the logs).

   e. For resources with mutable labels  (like Disks, for which attachment state may have changed),
   override `relabel_on_cron()` and return `True`. This will allow Cloud Scheduler  to relabel them. (This is because we label
   on-event only for on creation , so Cloud Scheduler is the way to relabel mutated state.)


2. Add your API to the `required_svcs` in `deploy.sh`.

3. Add your Google Cloud API "methods" to `log_filter` in `deploy.sh`.
    * `methodName` is part of the logs generated on creation.
    * See examples of such logs in `sample_data` directory.
        * E.g., you can see a log sample for bucket creation, in file `sample_data/storage.buckets.create.log_message.json`. (Or create a bucket and look at the log.)
        * In that file you see `"methodName": "storage.buckets.create"`.

4. Add permissions in `iris-custom-role.yaml` to be granted to the Iris custom role. This role allows  Iris, for each resource type, to list, get, and update. (Updating means permission `setLabels` where available  or permission `update`  otherwise.)

# Testing

## Integration test

* `integration_test.sh` creates a Google App Engine app and cloud resources and tests against them. See the file for
  instructions.
* It's an easy sanity check to be sure that, for example, that you have the right permissions.
* It works against two test projects that you specify.

## Testing the Cloud Scheduler scheduled labeling

- This is less automated than `integration_test.sh`, so do it only if you have special need to test this functionality.
- Deploy some cloud resources like Cloud SQL instance. Or deploy an unattached disk and attach it.
- Configuration
    * Optionally edit the configuration file to set `label_all_on_cron: True` or `False`.
      `True` will cause all resources to be labeled on the Cloud Scheduler cron job, while
      `False` will cause only Cloud SQL and GCE Disks to be labeled.
    * Edit the configuration file to set `iris_prefix` to a unique value, so you can track the labels generated by this
      test.
- Deploy the app
    * Use the `-c` switch at the end of the line (after the project ID). This disables event-based labeling, keeping
      only the Cloud Scheduler cron functionality.
    * Trigger Cloud Scheduler from the App Engine GUI, and check that labels were added.

# Next steps

See `TODO.md` for potential future improvements.
