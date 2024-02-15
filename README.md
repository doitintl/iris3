# Iris

In Greek mythology, Iris(Ἶρις) is the personification of the rainbow and messenger of the gods. She was the handmaiden
to Hera.

# Blog post

See
the [post that presents Iris](https://blog.doit-intl.com/iris-3-automatic-labeling-for-cost-control-7451b480ee13?source=friends_link&sk=b934039e5dc35c9d5e377b6a15fb6381).

# What Iris does for you

Iris automatically assigns labels to Google Cloud Platform resources for manageability and easier billing reporting.

Resources of all supported types in all or some of the projects in the GCP organization will get automatically-generated labels with keys like `iris_zone` (the prefix is configurable), and a value copied from the resource. For example, a Google
Compute Engine instance would get labels like
`[iris_name:nginx]`, `[iris_region:us-central1]` and `[iris_zone:us-central1-a]`. This behavior can be configured in
various ways; see below.

## Note: Organization focus

Note that Iris is designed to serve the organization. It is not designed around serving a single project (though you can configure that).

## Iris doesn't add new information

Iris does not *add* information, only *copy* values that already exist. For example, it can label a VM instance with its zone; but it cannot add a "business unit" label because it does not know a resource's business unit. For that, you should label all resources when creating them, e.g., in your Terraform scripts. (Indeed, iris can be made extraneous in this way.)

## Existing resources are not all labeled (by default)

If you want to label lots of virtual machines,PubSub topics etc. that *already exist* when you install Iris, see section "[Labeling existing resources](#labeling-existing-resources)" below.

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
* To do this, deploy Iris with `label_all_on_cron: True` and wait for the next scheduled run, or manually trigger a run   through Cloud Scheduler.
* Thenּ, you may want to then **redeploy** Iris with `label_all_on_cron: False`, to avoid the resource consumption of  relabeling all resources with the same label every day forever.

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

### Org and IAM

* You can deploy Iris in any project within your Google Cloud organization, but we recommend using a
  [new project](https://cloud.google.com/resource-manager/docs/creating-managing-projects#creating_a_project).

* Here are the required organization-level roles for you, the deployer, to allow the deploy script to set up roles and  log sink. (Note that *Organization Owner* is not enough).
    * *Organization Role Administrator*  so the deployment script can create a custom IAM role for Iris that allows it to  get and set labels.
    * *Security Admin* so the deployment script can grant the needed role bindings, e.g., to the App Engine service account.
    * *Logs Configuration Writer* so the deployment script can create an organization log sink that sends logs to
      PubSub.

* The required project-level roles: *Project Owner* or *Project Editor* on the project where Iris is deployed, so that the deployment script can create role bindings, topics and subscriptions, and deploy App Engine. Fine-granted "predefined roles" are not possible because deploying Cloud Scheduler cron requires at least Editor or Owner, per GCP docs.

### App Engine Defaults


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
* For options, run `deploy.sh -h` for documentation on usage of command-line options.
 
* When the labeling occurs
  * By default, labeling occurs on resource-creation, and also using Cloud Scheduler ("cron"). Each of these types works on certain resource types and not others (see [Supported Google Cloud Labels](#Supported Google Cloud Labels) above), depending on configuration (`config.yaml`).
  * Use `-c` switch on `deploy.sh` to label using Cloud Scheduler only.
  * Use `-e` switch on `deploy.sh` to label on-event only.
  * If you use **both** `-c` and `-e` or **neither**, both types of labeling occur.
  * If you change from having Cloud Scheduler labeling to not having it, or vice versa, be sure to deploy both org-level and project-level elements , not just project elements, since this involves the org-level sink.
* Organization-level and project-level elements
  * First, note that Iris is an organization-level application. Iris labels all projects in an org (unless you filter it down). Iris has architecture elements which are deployed to both the org and the project.
  * By default, deployment is of both  organization-level elements (e.g., Log Sinks) and project-level elements (e.g., App Engine app). In general, you can just use this default every time you redeploy. 
  * Alternatively, you can have a person without org-level permissions redeploy only the project-level elements (e.g. when you change configuration), after the first deployment. Do this with the `-p` switch on `deploy.sh`.
  * Likewise, org-level elements only are deployed when you use the `-o` switch on `deploy.sh`.
  * If you use **both** `-p` and `-o` or **neither**, both types of elements are deployed.

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
* Run `uninstall.sh -h` for help.
* See a comment in `uninstall.sh` that describes what elements are uninstalled.
* A full uninstall will also delete the custom role. This will then block you from re-deploying  unless you first either undelete the custom role or else give a new custom-role name at the top of `custom-iris-role.yaml`.

# Architecture

* Iris runs in Google App Engine Standard Environment (Python 3).
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
    * A dead-letter subscription. This is a pull subscription. By default, it just accumulates the messages. You can use      it to see statistics, or you can pull messages from it.

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
    * Use `test_do_label` and `test_label_one` and `test_schedule` to trigger against your localhost dev-server, to
      label actual Cloud resources that you pre-deploy.
        * See the `test_...` files for instructions.

## Adding new kinds of labels

Iris adds about twenty kinds of labels. More can be added, but don't add too many: Billing analytics work best when not swamped by excess labels. This is why Iris does not implement all possible labeling, say by automatically copying all fields from each resource into labels.

### Developing new labels for an existing resource type

To add a new label key to an existing resource type, add `_gcp_<LABEL_NAME>` methods (like `_gcp_zone()`) in the relevant file in `/plugins`, following the example of the existing ones. Labels will be added with a key from the function name (`zone` in that example), and a value returned by the function (in our example, the zone identifier).

For example, you might want to add a label identifying the creator of a resource, or add the name of the topic to its subscriptions.

### Supporting new resource types

Iris is easily extensible with plugins, to support labeling of other GCP resources. Use existing files in `/plugins` as
examples.

1. Create a Python file in the `/plugins` directory, holding a subclass of `Plugin`.

   a. The filename and class name take the form: `cloudsql.py` and `Cloudsql`. That's lowercase and Titlecase. (Only the
   first character is capitalized, even in multiword names.) The two names should be the same except for case.

   b. Implement abstract methods from the `Plugin` class.

   c. Add `_gcp_<LABEL_NAME>` methods (like `_gcp_zone()`). Labels will be added with a key from the function
   name (`zone` in that example), and a value returned by the function
   (in our example, the zone identifier).

   d. For resources that cannot be labeled on creation (like CloudSQL, which takes too long to initialize), you should
   override `is_labeled_on_creation()` and return `False`  (though if you don't, the only bad-side effect will be errors
   in the logs).

   e. For resources with mutable labels  (like Disks, for which attachment state may have changed), override `relabel_on_cron()` and return `True`. This will allow Cloud Scheduler to relabel them. (This is because after a resource is created and possibly labeled, so Cloud Scheduler is the way to relabel mutated state.)

2. Add your API to the `required_svcs` in `deploy.sh`.

3. Add your Google Cloud API "methods" to `log_filter` in `deploy.sh`.
    * `methodName` is part of the logs generated on creation.
    * See examples of such logs in `sample_data` directory.
        * E.g., you can see a log sample for bucket creation, in
          file `sample_data/storage.buckets.create.log_message.json`. (Or create a bucket and look at the log.)
        * In that file you see `"methodName": "storage.buckets.create"`.

4. Add permissions in `iris-custom-role.yaml` to be granted to the Iris custom role. 
   * This role allows Iris, for each resource type, to list, get, and update. 
     * ("Update" requires permission `setLabels` where available or permission `update`  otherwise.) 
     * The name of this role is `iris3`by default, but may be set by passing env variable `IRIS_CUSTOM_ROLE` in calling `deploy.sh` or `uninstall.sh`

# Testing
## Circuit-breaker
Warning: A circuit breaker will cause scheduled labeling to fail with an exception if you are running in "development/test mode" and scheduled-labeling finds more than 3 projects to label. This is meant to protect from accidentally flooding thousands of projects with labels when you are testing. (Though if so, the worst that happens is some useful labels 😉 )

  * "Development/test mode" means that at least one of these is true:
    * The project ID has in it `dev`, `qa`, `playground`, or `test`, or whatever is configured. You can change or remove these strings in the configuration under key `test_or_dev_project_markers`)
    * or `config-test.yaml` exists, so that Iris is using it rather than `config.yaml`
    * or Iris is running in your local machine (rather than App Engine)

## Integration test

* `integration_test.sh` creates a Google App Engine app and cloud resources and tests against them. See the file for
  instructions.
* It's an easy sanity check to be sure that, for example, that you have the right permissions.
* It works against two test projects that you specify.

## Testing the Cloud Scheduler scheduled labeling

- This testing is less automated than `integration_test.sh`, so do it only if you have special need to test this functionality.
- Deploy some cloud resources like Cloud SQL instance. Or deploy an unattached disk and attach it.
- Configuration
    * Optionally edit the configuration file to set `label_all_on_cron: True` or `False`.
      * `True` will cause all resources to be labeled on the Cloud Scheduler cron job, 
      * and `False` will cause only Cloud SQL and GCE Disks to be labeled.
    * Edit the configuration file to set `iris_prefix` to a unique value, so you can track the labels generated by this test.
- Deploy the app
    * Use the `-c` switch at the end of the line (after the project ID). This disables event-based labeling, keeping only the Cloud Scheduler cron functionality.
    * Trigger Cloud Scheduler from the App Engine GUI, and check that labels were added.

# Next steps

See `TODO.md` and GitHub issues for potential future improvements.
