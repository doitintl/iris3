# Iris
See the [blog post about Iris 3](https://blog.doit-intl.com/iris-3-automatic-labeling-for-cost-control-7451b480ee13?source=friends_link&sk=b934039e5dc35c9d5e377b6a15fb6381).

In Greek mythology, Iris (/ˈaɪɹɪs/; Greek: Ἶρις) is the personification of the rainbow and messenger of the gods. 
She was the handmaiden to Hera.

## Iris3 vs Iris

This is a complete rewrite of [Iris](https://github.com/doitintl/iris), replatforming it to AppEngine Python 3, 
adding functionality, and fixing bugs. See the change logs [below](#change-log).

## What it does for you

Iris automatically assigns labels to Google Cloud resources for manageability and easier billing reporting. 

Each resource in a Google Cloud Platform Organization will get automatically generated labels
with a key like `iris_zone` (the prefix is configurable), and the relevant value.
For example, a Google Compute Engine instance would get labels like
`[iris_name:nginx]`, `[iris_region:us-central1]` and `[iris_zone:us-central1-a]`.

## When it does it
Iris does this in two ways:
* On resource creation, by listening to Operations (Stackdriver) Logs. 
(You can disable this, see ["Deploy"](#deploy).)
* On schedule, using a cron job. (Configurable in `cron.yaml`.) 
Some types of resources only get labeled on schedule.

## Supported Google Cloud Products

Right now, there are plugins for the following types of resources.
* Compute Engine Instances (including  preemptible instances or instances created by Managed Instnace Groups.)
* Compute Engine Disks
* Compute Engine Snapshots
* Cloud Storage
* BigQuery Datasets
* BigQuery Tables
* BigTable Instances
* PubSub Subscriptions
* PubSub Topics
* CloudSQL (These receive a label only on the cron schedule, not on creation.)

## Installation

We recommend deploying Iris in a
[new project](https://cloud.google.com/resource-manager/docs/creating-managing-projects#creating_a_project)
within your Google Cloud organization. 

To deploy, you will need to have these roles on the the *organization* where Iris is deployed.
* *Organization Role Administrator* to create a custom IAM role for Iris that allows to get and set labels on the services.
   (Note that this is different from *Organization Administrator* and from Organization *Owner*.)
 * *Security Admin* OR *Organization Administrator*  to allow Iris app engine service account to use the above role
 * *Logs Configuration Writer* to create an organization log sink that sends logs to PubSub

On the project where Iris3 is deployed, you will need Owner or these roles:
 * Project IAM Admin
 * App Engine Admin 
 * Pub/Sub Admin


## Deploy
* Optionally edit `app.yaml`, changing the secret token for PubSub.
* Check you have Python 3.8+ as your default `python3`.
* Run `./deploy.sh <PROJECT_ID>`. 
   * Add `-c` at the end to use only cron, without labeling on-demand, to save costs on the log sink.

## Configuration

* See  `config.yaml` for documentation of these options:
  - What projects to include. (The default is all projects in the organization.)
  - A prefix for all label keys (so, if the prefix is `iris`, labels will look like `iris_name` etc.)
  - Whether to copy all labels from the project into resources in the project.
* See [above](#deploy) for disabling the on-event labeling
* `cron.yaml` lets you change the scheduled labelings.

## Local Development
For local development, run `main.py` as an ordinary Flask application, either by running the module,
or with `export FLASK_ENV=development;export FLASK_DEBUG=1; python -m flask run --port 8000`

### Prerequisites for developing and building
* In development
```
pip install -r requirements.txt
pip install -r requirements-test.txt
```
* Install `envsubst` and `jq`
* Install and initialize `gcloud`

### Developing new labels

To add a new label to an existing resource type, just create 
a method `_gcp_<LABEL_NAME>` on the example of the existing ones.

For example, you might want to add a label identifying
the creator of a resource, or add the name the topic to its
subscription.

But don't add too many: The reason that not all
fields are in billing data is that there are a lot of them!

### Developing new resource types

Iris is easily extensible with plugins, to support labeling of other GCP resources. 

1. Create a Python file in the `/plugins` directory, holding a subclass of `Plugin`. 
    a. The filename and class name take the form: `cloudsql.py` and `Cloudsql`.
    That's lowercase and Titlecase. (Only the first character is capitalized, even in multiword names.)
    Otherwise, the two names should be the same.

    b. Implement abstract methods. 
    
    c. Add `_gcp_<LABEL_KEY>` methods (like `_gcp_zone()`). Labels will be 
    added with a key from the function name (`zone` in that example),
    and a value returned by the function (the actual zone value in the example, 
    retrieved, using the Google API, in the function `_gcp_zone()`).

    d. Override `is_labeled_on_creation()` and return `False` if the
    resource cannot be labeled on creation (like CloudSQL), though 
    if you don't, the only bad side effect will be errors in the logs.

2. Add your methods to `log_filter` in `deploy.sh` 
3. Add roles in `roles.yaml` allowing Iris to list, get, and 
update (add labels to) your resources.

### Testing

#### For debugging 
`test_do_label` and `test_label_one` work against your localhost dev-server, and 
with resources that you pre-deploy. See the files for instructions.

####  Integration test
`integration_test.sh` tests agaist a deployed app and deployed cloud resources.
See the file for instructions.

#### Testing the scheduled labeling
Deploy some resources, deploy  the app with the `-c` switch  to disable event-based labeling,
then trigger cron from the App Engine GUI, and check that labels were added. 

## Change log 
(Iris 3 as compared to Iris)
1. Porting to Python 3 version of Google App Engine Standard Environment. 
(The Python 2 version is long since obsolete, not well-supported, and some necessary
APIs cannot be used with it.)
1. Labeling for PubSub Topics and Subscriptions
1. Project labels can be automatically copied into each resource in the project.
1. Option to choose the projects in which resources that will be labeled;
or to label across the entire organization.
1. Option to save costs by using only cron, without labeling on demand.
1. Automated tests
1. Easier plugin development: 
    * Less need to configure a list of permitted labels or of "on-demand" plugins
    * Abstract methods clarify what needs to be implemented
    * `_gcp_` prefix rather than `_get_` highlights the dynamically-invoked 
    methods also distinguishing them from getters
    * More functionality in base classes, minimizing the amount of implementation needed
    for each plugin
1. Bug fix: Deployment was failing for certain project names.
1. Simple authentication for cron endpoint and PubSub Push endpopint.
1. Expanded documentation
1. Optimization: Do not attempt to set labels if labels have not changed.

## Next steps
See `TODO.md` for potential future improvements.
