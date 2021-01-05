# Iris

[Blog Post](https://blog.doit-intl.com/auto-tagging-google-cloud-resources-6647cc7477c5)

In Greek mythology, Iris (/ˈaɪrɪs/; Greek: Ἶρις) is the personification of the rainbow and messenger of the gods. Iris was mostly the handmaiden to Hera.

Iris helps automatically assign labels to Google Cloud resources for better manageability and billing reporting. Each resource in Google Cloud will get an automatically generated label in a form of [iris_name:name], [iris_region:region] and finally [iris_zone:zone]. For example if you have a Google Compute Engine instance named `nginx`, Iris will automatically label this instance with [iris_name:nginx], [iris_region:us-central1] and [iris_zone:us-central1-a].

Iris will also label short-lived Google Compute Engine instances such as preemptible instances or instances managed by an Instance Group Manager by listening to Operations (Stackdriver) Logs and adding required labels on-demand. 

**Supported Google Cloud Products**

Iris is extensible through plugins. 
Right now, there are plugins for the following products:

* Google Compute Engine Disks
* Google Compute Engine Snapshots
* Google Cloud Storage
* Google CloudSQL (not yet implemented)
* Google BigQuery
* Google BigTable

**Installation**

We recommend deploying Iris in a
[new project](https://cloud.google.com/resource-manager/docs/creating-managing-projects#creating_a_project)
within your Google Cloud organization. 

You will need the following IAM permissions on your Google Cloud organization to complete the deployment: 

 * App Engine Admin
 * Logs Configuration Writer
 * Pub/Sub Admin

##### Install dependencies

`pip install -r requirements.txt -t lib`

##### Deploy
`./deploy.sh <project-id>`

##### Configuration

Configuration is stored in the `config.json` file, which includes.

1. `labels` - A list of labels that will be applied to the resources 
(if the plugin implements a function by the name _get_<LABELNAME>)
2. `on_demand` - A list of plugins that will label whenever
there is a new object of their type (as opposed to labeling 
at application startup or on schedule).

### Local Development
For local development, edit `dev_config.json` and run `main.py` as an ordinary Flask application.

## Extension
Iris is easily extendable to support labeling of other GCP services. 
You will need to create a Python file in the `/plugins` directory,
with a subclass of `Plugin`. The Python file and class name should be the same, except 
for case. (The filename should be lowercase.)
 
In addition to implementing abstract methods, you will need `_get_<LABELNAME>` methods
This application will add labels that are defined in the `config.json` file
but only if `_get_<LABELNAME>` method is defined in the relevant plugin/
