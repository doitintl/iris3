# Iris

In Greek mythology, Iris (/ˈaɪrɪs/; Greek: Ἶρις) is the personification of the rainbow and messenger of the gods. She
was the handmaiden to Hera.

# Blog post

See
the [post that presents Iris](https://blog.doit-intl.com/iris-3-automatic-labeling-for-cost-control-7451b480ee13?source=friends_link&sk=b934039e5dc35c9d5e377b6a15fb6381)
.

## What it does for you

Iris automatically assigns labels to Google Cloud resources for manageability and easier billing reporting.

Each resource in a Google Cloud Platform Organization will get automatically-generated labels with keys
like `iris_zone` (the prefix is configurable), and the relevant value.  
For example, a Google Compute Engine instance would get labels like
`[iris_name:nginx]`, `[iris_region:us-central1]` and `[iris_zone:us-central1-a]`.

Importantly, Iris cannot *add* information, only *copy* information. For example, it can label a VM instance with its
zone, since this information is known; but it cannot add a "business unit" label because it does not know what business
unit a resource is launched from.

Iris is open-source: Feel free to add functionality and add new types of labels. See the `TODO.md` file for features and fixes
you might do.

## When it does it

Iris adds labels:

* On resource creation, by listening to Google Cloud Operations (Stackdriver) Logs.
    - You can disable this, see ["Deploy"](#deployment).
* On schedule, using a Cloud Scheduler cron job that the deployer sets up for you. 
    - See  [Configuration section below](#configuration) below for details.
    - You can configure whether all resources get labeled during the cron run or just the ones that need
    it because they cannot be labeled on-event. (See `label_all_on_cron` below.)
      
## Supported Google Cloud Products

Right now, there are plugins for the following types of resources. To learn what label keys are added, search
for `def _gcp_<LABEL_NAME>)`, i.e., functions whose names start `_gcp_`. The part of the function name after `_gcp_` is
used for the label key.  

These are also listed below.

* Compute Engine Instances (Labels name, zone, region, instance type)
    * Including preemptible instances or instances created by Managed Instance Groups.
    * But: GKE Nodes are not labeled, as doing so recreates them.
* Compute Engine Disks (Labels name, zone, region)
    * But: GKE Disks (Volumes) are not labeled. See above.
    * Disks created with an Instance are not labeled on-creation. They are labeled with the Cloud Scheduler cron job.
    * The label indicating whether a disk is attached will change, if the state changed, on the cron job, not on-event.
* Compute Engine Snapshots  (Labels name, zone, region)
* Cloud Storage  (Labels name, zone, region)
* BigQuery Datasets (Labels name, zone, region)
* BigQuery Tables (Labels name, zone, region)
* BigTable Instances (Labels name, zone, region)
* PubSub Subscriptions (Labels name)
* PubSub Topics (Labels name, zone)
* CloudSQL (Labels name, zone, region)
    * These receive a label only on the Cloud Scheduler cron job, not on creation.
* Google Cloud Storage buckets  (Labels name, location)
* In addition to these, project labels may be copied into each resource,
  if you have configured that in `config.yaml`,

## Installation

### Before deploying

You can deploy Iris in any project within your Google Cloud organization, but we recommend using a
[new project](https://cloud.google.com/resource-manager/docs/creating-managing-projects#creating_a_project).

To deploy, you will need to have these roles on the *organization* where Iris is deployed.

* *Organization Role Administrator* to create a custom IAM role for Iris that allows to get and set labels on the
  services.
  (Note that this is different from *Organization Administrator* and from Organization *Owner*.)
* *Security Admin* OR *Organization Administrator*  to allow Iris app engine service account to use the above role
* *Logs Configuration Writer* to create an organization log sink that sends logs to PubSub

On the project where Iris is deployed, you will need Owner or these roles:

* *Project IAM Admin* to set up the custom role as mentioned above.
* *App Engine Admin* to deploy to App Engine.
* *Pub/Sub Admin* to create topics and subscriptions.

### Deployment

* Have Python 3.8+ as your default `python3`.
* Install tools  `envsubst` and `jq`.
* Install and initialize `gcloud` to an account with the [above-mentioned](#before-deploying) roles
* Optionally configure by editing `config.yaml` (use `config.yaml.original` as , `cron.yaml`, or `app.yaml`. See [Configuration](#configuration) below.
* Run `./deploy.sh <PROJECT_ID>`.
    * Add `-c` at the end to use only Cloud Scheduler cron (i.e., without labeling on-creatio).
        * With `-c`, resources will get labeled only by cron. This saves costs.
        * See below re the `label_all_on_cron` setting in  `config.yaml`.
* If you redeploy different versions of Iris code.
    * If new plugins were added or some removed, the log sink *will* be updated to reflect this.
    * If the parameters for subscriptions or topics were changed in a new version of the Iris code, the subscriptions
    or topics will not be updated. You would have to delete them first.
    
### Configuration

* See `config.yaml` for documentation of these options:
    - What projects to include. (The default is all projects in the organization.)
    - A prefix for all label keys (so, if the prefix is `xyz`, labels will look like `xyz_name` etc.)
    - Whether to copy all labels from the project into resources in the project.
    - Whether the Cloud Scheduler cron job should label all types of resources. 
        - If True, then on cron job, Iris scans and labels *all* resources in all projects 
            - Setting this to `True` may be useful for a first run, to label existing resources.
        - If False, then on cron job, Iris labels just the types that need it, because they cannot be 
            labeled in full on-event
            (Cloud SQL and Disks).
    - You can also change the secret token for PubSub here. 
        - The security this provides is real, particularly if your GCP project is secure, but not strong.
    
* `app.yaml` lets you configure App Engine. See App Engine documentation.

* See the `-c` switch on `deploy.sh` discussed in ["Deployment" above](#deployment) for disabling the on-event labeling 
  and using only Cloud  Scheduler cron.
* `cron.yaml` lets you change the timing for the Cloud Scheduler scheduled labelings.

## Architecture

* Iris runs in Google App Engine Standard Environment (Python 3).
* The cron job is run in Cloud Scheduler (see `cron.yaml`)
* A Log Sink on the organization level sends all logs about resource-creation to a PubSub topic.
    * The Log Sink is filtered to include only supported resource types and (if configured) 
      only specific projects.
* PubSub topics:
    * One receives the logs from the Log Sink on resource creation.
    * The other receives messages sent by the `/schedule` Cloud Scheduler handler in `main.py`, which is triggered by
      the Cloud Scheduler.
        * Such messages are an instruction to call `do_label` for each 
          combination of (project, resource-type).
    * A dead-letter topic      
* PubSub subscriptions
   * One for each topic: These direct the messages to `/label_one` and `/do_label` in `main.py`, respectively
   * A dead-letter subscription. This is a pull subscription. By default it just accumulates the messages.
     You can use it just to see statistics, or you can pull messages from it.  
* IAM Roles
    * See the ["Before Deploying" section above](#before-deploying)

## Local Development

### Development tools

* Prerequisites for developing and building. 
    * See [Installation](#installation))
    * Also, for development, set up a virtual env and run `pip3 install -r requirements.txt`
* Run the server locally
    * Run `main.py` as an ordinary Flask application as follows:
        * To use the command-line,
          use `export FLASK_ENV=development;export FLASK_RUN_PORT=8000;export FLASK_DEBUG=1;FLASK_APP=main.py python -m flask run`
        * In an interactive development environment, run `main.py`, first setting these environment variables.
* For hands-on debugging
    * Set the projects you want to use in  `config.yaml`
    * Use `test_do_label` and `test_label_one` and `test_schedule` to trigger against your localhost dev-server, 
      to label actual Cloud resources that you pre-deploy. 
      * See these `test_...` files for instructions.


### Adding new labels
Iris adds about twenty kinds of labels. More can be added, but don't add too many. Billing analytics work best when they are not swamped by excess labels.
This is why GCP doesn't simply add these labels,  and why Iris does not implement all possible labeling, say by automatically copying all fields from each resource into 
labels.

#### Developing new labels for an existing resource type

To add a new label key to an existing resource type, 
add `_gcp_<LABEL_NAME>` methods (like `_gcp_zone()`)  in the relevant file in `/plugins`, following the example of the existing ones.
Labels will be added with a key from the function name (`zone` in that example), and a value returned by the function
(in our example, the zone identifier).

For example, you might want to add a label identifying the creator of a resource, or add the name the topic to its subscription.

#### Supporting new resource types

Iris is easily extensible with plugins, to support labeling of other GCP resources. 
Use existing files in `/plugins` as examples.

1. Create a Python file in the `/plugins` directory, holding a subclass of `Plugin`.

   a. The filename and class name take the form: `cloudsql.py` and `Cloudsql`. 
   That's lowercase and Titlecase. (Only the first character is capitalized, even in multiword names.)
   The two names should be the same except for case.

   b. Implement abstract methods from the `Plugin` class.

   c. Add `_gcp_<LABEL_NAME>` methods (like `_gcp_zone()`). 
   Labels will be added with a key from the function name (`zone` in that example), and a value returned by the function
   (in our example, the zone identifier).

   d. For resources that cannot be labeled on creation (like CloudSQL, which takes too long to initialize),
   override `is_labeled_on_creation()` and return `False`
   (though if you don't, the only bad side effect will be errors in the logs).

   e. For resources with mutable labels  (like Disks, for which
   attachment state may have changed), override `relabel_on_cron()` and return `True`. This will allow
   Cloud Scheduler cron to relabel them. (We label on-event only for creation events, so Cloud Scheduler is the way
   to relabel mutated state.)

   f. For resources where labeling must be skipped under certain conditions (like GCE Instances, where labeling must be
   skipped for GKE Nodes, as doing so would cause them to be replaced), override `block_labeling()` and return `True`
   where needed.

2. Add your Google Cloud API "methods" to `log_filter` in `deploy.sh`.
    * `methodName` is part of the logs generated on creation.
    * See examples of such logs in `sample_data` directory.
        * E.g., you can see a log sample for bucket creation, in
          file `sample_data/storage.buckets.create.log_message.json`.
          (Or create a bucket and look at the log.)
        * In that file you see `"methodName": "storage.buckets.create"`.

3. Add roles in `roles.yaml` allowing Iris to list, get, and update (add labels to) your resources.

### Testing

#### Integration test

* `integration_test.sh` creates a Google App Engine app and cloud resources and tests against them. 
  See the file for instructions.
* It's an easy sanity check to be sure that, for example, that you have the right permissions.
* It works against two test projects that you specify.

#### Testing the  Cloud Scheduler scheduled labeling

- This is less automated than `integration_test.sh`, so do it only if you have special need to test this functionality.
- Deploy some cloud resources like Cloud SQL instance. Or deploy an unattached disk and attach it.
- Configuration
    * Optionally edit `config.yaml` to set `label_all_on_cron: True` or `False`. 
      `True`  will cause all resources to be labeled on the Cloud Scheduler cron job, while
      `False` will cause only Cloud SQL and GCE Disks to be labeled.
    * Edit `config.yaml` to set `iris_prefix` to a unique value so you can track the labels generated by this test.
- Deploy the app
    * Use the `-c` switch at the end of the line(after the project ID). This disables event-based labeling so you can
      focus on the Cloud Scheduler cron functionality.
    * Trigger Cloud Scheduler from the App Engine GUI, and check that labels were added.

## Change log

This is a complete rewrite of [Iris](https://github.com/doitintl/iris), replatforming it to AppEngine Python 3, adding
functionality, and fixing bugs.

1. Porting to Python 3 version of Google App Engine Standard Environment.
   (The Python 2 version is long since obsolete, not well-supported, and some necessary APIs cannot be used with it.)
1. Labeling for PubSub Topics and Subscriptions
1. Project labels can be automatically copied into each resource in the project. See `config.yaml`
1. Option to choose the projects in which resources that will be labeled; or to label across the entire organization.
1. Option to save costs by using only Cloud Scheduler cron, without labeling on demand.
1. Automated tests
1. Easier plugin development:
    * Less need to configure a list of permitted labels or of "on-demand" plugins
    * Abstract methods enforce what needs to be implemented
    * `_gcp_` prefix rather than `_get_` highlights the dynamically-invoked methods, also distinguishing them more
      clearly from getters.
    * More functionality in base classes, minimizing the amount of implementation needed for each plugin
1. Bug fix: Deployment was failing for certain project names.
1. Simple authentication for cron endpoint and PubSub Push endpopint.
1. Expanded documentation
1. Optimization: Do not attempt to set labels if labels have not changed.
1. Support "disk is attached" tag, and mutating it when status changes
1. Improve performance and scalability, to save costs.

## Next steps

See `TODO.md` for potential future improvements.
