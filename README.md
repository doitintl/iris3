# Iris

[Blog Post](https://blog.doit-intl.com/auto-tagging-google-cloud-resources-6647cc7477c5)

In Greek mythology, Iris (/ˈaɪrɪs/; Greek: Ἶρις) is the personification of the rainbow and messenger of the gods. 
She was the handmaiden to Hera.

Iris automatically assigns labels to Google Cloud resources for manageability and easier billing reporting. 

Each resource in Google Cloud, in the entire GCP organization, will get an automatically generated label 
with key `iris_name`, `iris_region`, `iris_zone`. `iris_zone`, and holding the relevant value.
For example if you have a Google Compute Engine instance named `nginx`, Iris will automatically label this instance 
with [iris_name:nginx], [iris_region:us-central1] and [iris_zone:us-central1-a].

Iris does this in two ways
* On the creation event, by listening to Operations (Stackdriver) Logs 
* On schedule, using a cron job

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

## Local Development
For local development, run `main.py` as an ordinary Flask application.

To choose the project for PubSub, either pass `IRIS_PROJECT` as a
environment variable, or make sure that `gcloud` has been initialized
to the project that you want as default.

## Supported Google Cloud Products

Right now, there are plugins for the following products. Not all Iris
labels are necessarily populatd for each one: It depends on whether the value
is relevant to the resource and whether the plugin implements the 
relevant `_get_<LABEL` function.
* Compute Engine Instances (including  preemptible instances or instances created by Managed Instnace Groups.)
* Compute Engine Disks
* Compute Engine Snapshots
* Cloud Storage
* CloudSQL (These receive a label only on the cron schedule, not on-creation.)
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
need `_get_<LABELNAME>` methods. 

If the resource cannot receive labels on-demand then also
override `is_labeled_on_creation` and return `False`.

