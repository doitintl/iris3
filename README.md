# Iris

See
the [blog post about Iris 3](https://blog.doit-intl.com/iris-3-automatic-labeling-for-cost-control-7451b480ee13?source=friends_link&sk=b934039e5dc35c9d5e377b6a15fb6381)
.

In Greek mythology, Iris (/ˈaɪɹɪs/; Greek: Ἶρις) is the personification of the rainbow and messenger of the gods. She
was the handmaiden to Hera.

## What it does for you

Iris automatically assigns labels to Google Cloud resources for manageability and easier billing reporting.

Each resource in a Google Cloud Platform Organization will get automatically-generated labels with a key
like `iris_zone` (the prefix is configurable), and the relevant value. For example, a Google Compute Engine instance
would get labels like `[iris_name:nginx]`, `[iris_region:us-central1]` and `[iris_zone:us-central1-a]`.

Importantly, Iris cannot *add* information, only *copy* information. For example, it can label a VM
instance with its zone, since this information is known; but it cannot add a "business unit" label because
it does not know what business unit a resource is launched from.

Iris is open-source: Feel free to add labels, and important, to *disable* functionality that adds certain labels 
(by deleting `_gcp_<LABEL_NAME` functions. The billing analytics in Google Cloud and 
DoiT International  Cloud Management Platform work best  when they are not swamped by excess labels.

## When it does it

Iris adds labels:

* On resource creation, by listening to Google Cloud Operations (Stackdriver) Logs.
  (You can disable this, see ["Deploy"](#deployment).)
* On schedule, using a Cloud Scheduler cron job that the deployer sets up for you. (Disable or configure ths in `cron.yaml`.)
  Some types of resources only get labeled on schedule.

## Supported Google Cloud Products

Right now, there are plugins for the following types of resources. To learn what label keys are added, search
for `def _gcp_<LABEL_NAMR>)`, i.e., functions whose names start `_gcp_`. The function name is used for the label key. These are also listed
below.

* Compute Engine Instances (Labels name, zone, region, instance type)
    * Including preemptible instances or instances created by Managed Instance Groups.
    * But: GKE Nodes are not labeled, as doing so recreates them.
* Compute Engine Disks (Labels name, zone, region)
    * But: GKE Disks (Volumes) are not labeled. See above.
* Compute Engine Snapshots  (Labels name, zone, region)
* Cloud Storage  (Labels name, zone, region)
* BigQuery Datasets (Labels name, zone, region)
* BigQuery Tables (Labels name, zone, region)
* BigTable Instances (Labels name, zone, region)
* PubSub Subscriptions (Labels name)
* PubSub Topics (Labels name, zone)
* CloudSQL (Labels name, zone, region)
    * These receive a label only on the cron schedule, not on creation.
* Google Cloud Storage buckets  (Labels name, location)
* In addition to these, project labels may be copied into each resource, if you have configured that in `config.yaml`,

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

On the project where Iris3 is deployed, you will need Owner or these roles:

* *Project IAM Admin* to set up the custom role as mentioned above
* *App Engine Admin* to deploy to App Engine
* *Pub/Sub Admin* to create topics and subscriptions

### Deployment

* Optionally edit `app.yaml`, changing the secret token for PubSub.
* Check you have Python 3.8+ as your default `python3`.
* Run `./deploy.sh <PROJECT_ID>`.
    * Add `-c` at the end to use only Cloud Scheduler cron (i.e., without labeling on-demand). 
      All resources will get labeled on-schedule. This saves costs on the log sink.

### Optional Configuration

* See `config.yaml` for documentation of these options:
    - What projects to include. (The default is all projects in the organization.)
    - A prefix for all label keys (so, if the prefix is `iris`, labels will look like `iris_name` etc.)
    - Whether to copy all labels from the project into resources in the project.
* See [above](#deployment   ) for disabling the on-event labeling.
* `cron.yaml` lets you change the scheduled labelings.

## Architecture
* Iris runs in Google App Engine Standard Environment (Python 3)
* The cron job is set up in Cloud Scheduler (see `cron.yaml`)
* A Log Sink on the organization level sends all logs about resource-creation to a PubSub topic 
   * The Log Sink is filtered to focus only on supported resource types and (if configured) specific projects
* Two PubSub topics:
   * One receives the mentioned logs from the Log Sink
   * The other receives a message from the `/schedule` handler in `main.py`, which is triggered by the Cloud Scheduler.
     * Such messages are an instruction to call `do_label` for each combination of (project, resource-type)
* PubSub subscriptions, one for each topic
  * These direct the messages to `/label_one` and `/do_label` in `main.py`, respectively
* IAM Roles
  * See [above](#before-deploying)
)

## Local Development
For local development, 
* Run the server locally
    * Run `main.py` As an ordinary Flask application
      * On a command-line, use `export FLASK_ENV=development;export FLASK_RUN_PORT=8000;export FLASK_DEBUG=1;FLASK_APP=main.py python -m flask run`
      * In an interactive development environment, run `main.py`, first setting these environment variables.
*  For hands-on debugging
   * `test_do_label` and `test_label_one` work against your localhost dev-server, against resources that you pre-deploy. 
  See these files for instructions.
*  Prerequisites for developing and building
   * In development

```
pip install -r requirements.txt
pip install -r requirements-test.txt
```

   * For  `deploy.sh` and `integration_test.sh`
   * Install tools  `envsubst` and `jq`
   * Install and initialize `gcloud`

### Developing new labels

To add a new label to an existing resource type, just create a method `_gcp_<LABEL_NAME>` on the example of the existing
ones.

For example, you might want to add a label identifying the creator of a resource, or add the name the topic to its
subscription.

But don't add too many: The reason that not all fields are already in  the billing data is 
that there are a *lot* of potential fields, and this can will swamp your data with irrelevances.

### Supporting new resource types

Iris is easily extensible with plugins, to support labeling of other GCP resources. Use existing
files in `/plugins` as examples.

1. Create a Python file in the `/plugins` directory, holding a subclass of `Plugin`. 
   
   a. The filename and class name take
   the form: `cloudsql.py` and `Cloudsql`. That's lowercase and Titlecase. (Only the first character is capitalized,
   even in multiword names.) Otherwise, the two names should be the same.

   b. Implement abstract methods. A convenient error message will of course tell you what these are,
   or look in `plugin.py`.   

   c. Add `_gcp_<LABEL_NAME>` methods (like `_gcp_zone()`). Labels will be added with a key from the function
   name (`zone` in that example), and a value returned by the function (in our example, the
   zone identifier).

   d. For some  resources that cannot be labeled on creation (like CloudSQL, which takes
   too long to initialize), override `is_labeled_on_creation()` and return `False`
   (though if you don't, the only bad side effect will be errors in the logs).

2. Add your methods to `log_filter` in `deploy.sh`
3. Add roles in `roles.yaml` allowing Iris to list, get, and update (add labels to) your resources.

### Testing
#### Integration test

`integration_test.sh` tests against a deployed app and deployed cloud resources. See the file for instructions.

#### Testing the scheduled labeling

Deploy some resources, deploy the app with the `-c` switch  (after the project ID)
to disable event-based labeling, then trigger Cloud Scheduler cron from the App Engine GUI, and check that labels were added.

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
    * `_gcp_` prefix rather than `_get_` highlights the dynamically-invoked methods, also 
      distinguishing them more clearly from getters.
    * More functionality in base classes, minimizing the amount of implementation needed for each plugin
1. Bug fix: Deployment was failing for certain project names.
1. Simple authentication for cron endpoint and PubSub Push endpopint.
1. Expanded documentation
1. Optimization: Do not attempt to set labels if labels have not changed.
1. Support "disk is attached" tag, and mutating it when status changes

## Next steps

See `TODO.md` for potential future improvements.
