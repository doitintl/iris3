# Iris

[Blog Post](https://blog.doit-intl.com/auto-tagging-google-cloud-resources-6647cc7477c5)

In Greek mythology, Iris (/ˈaɪɹɪs/; Greek: Ἶρις) is the personification of the rainbow and messenger of the gods. 
She was the handmaiden to Hera.

Iris automatically assigns labels to Google Cloud resources for manageability and easier billing reporting. 

Each resource in Google Cloud, in the entire GCP organization (or a configured subset of projects)
will get an automatically generated label 
with key `iris_name`, `iris_region`, `iris_zone`. `iris_zone`, and the relevant value.
A Google Compute Engine instance named `nginx`, would be labeled, for example, 
with [iris_name:nginx], [iris_region:us-central1] and [iris_zone:us-central1-a].

Iris does this in two ways
* On the creation event, by listening to Operations (Stackdriver) Logs.
* On schedule, using a cron job, now scheduled to run every 12 hours. (See `cron.yaml`.) Some types
of resources only get labeled on schedule.

## Installation

We recommend deploying Iris in a
[new project](https://cloud.google.com/resource-manager/docs/creating-managing-projects#creating_a_project)
within your Google Cloud organization. 

You will need the following IAM permissions on your Google Cloud _organization_ (not just the project) 
to complete the deployment: 

 * App Engine Admin
 * Logs Configuration Writer
 * Pub/Sub Admin

## Deploy
* Optionally edit `app.yaml`, changing the secret token for PubSub.
* Run  `./deploy.sh <project-id>` 

## Configuration

Configuration is stored in the `config.yaml`, and is documented there.
Options for configuration include:
- What projects to include (The default is all projects in the organization).
- A prefix for all label keys (so, if it is `iris3`), labels will look like `iris_name` etc.
- Whether to copy all labels from the project into resources in the project as they are labeled.
- Which potential label keys to include (such as name, zone, etc.) However, a given plugin
will be able to apply a key only if it has a function `_get_<KEY_NAME>`

## Local Development
For local development, run `main.py` as an ordinary Flask application.


## Supported Google Cloud Products

Right now, there are plugins for the following types of resources.
* Compute Engine Instances (including  preemptible instances or instances created by Managed Instnace Groups.)
* Compute Engine Disks
* Compute Engine Snapshots
* Cloud Storage
* CloudSQL (These receive a label only on the cron schedule, not on creation.)
* BigQuery Datasets
* BigQuery Tables
* BigTable
* PubSub Subscriptions
* PubSub Topics

## Plugin development

Iris is easily extensible to support labeling of other GCP resources. 
Create a Python file in the `/plugins` directory,
holding a subclass of `Plugin`. 

The Python file and class-name should be the same, except for case:
The filename should be lowercase and the class name should be in Titlecase.
(Only the first character should be in upper case.)
 
In each class, in addition to implementing abstract methods, you will 
need `_get_<KEYNAME>` methods. Override `is_labeled_on_creation` and return
`False` if the  resource cannot be labeled on creation.

If the resource cannot receive labels on-demand then also
override `is_labeled_on_creation` and return `False`.

