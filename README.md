# Iris

[Blog Post](https://blog.doit-intl.com/auto-tagging-google-cloud-resources-6647cc7477c5)

In Greek mythology, Iris (/ˈaɪrɪs/; Greek: Ἶρις) is the personification of the rainbow and messenger of the gods. Iris was mostly the handmaiden to Hera.

Iris helps to automatically assign labels to Google Cloud resources for better manageability and billing reporting. Each resource in Google Cloud will get an automatically generated label in a form of [iris_name:name], [iris_region:region] and finally [iris_zone:zone]. For example if you have a Google Compute Engine instance named `nginx`, Iris will automatically label this instance with [iris_name:nginx], [iris_region:us-central1] and [iris_zone:us-central1-a].

Iris will also label short-lived Google Compute Engine instances such as preemptible instances or instances managed by an Instance Group Manager by listening to Operations (Stackdriver) Logs and adding required labels on-demand. 

**Supported Google Cloud Products**

Iris is extensible through plugins. New Google Cloud products may be supported via simply adding a plugin. Right now, there are plugins for the following products:

* Google Compute Engine (including disks and snapshots)
* Google Cloud Storage
* Google CloudSQL
* Google BigQuery
* Google Bigtable

**Installation**

We recommend deploying Iris in a [new project](https://cloud.google.com/resource-manager/docs/creating-managing-projects#creating_a_project) within your Google Cloud organization. You will need the following IAM permissions on your Google Cloud organization to complete the deployment: 

 * App Engine Admin
 * Logs Configuration Writer
 * Pub/Sub Admin

##### Install dependencies

`pip install -r requirements.txt -t lib`

##### Deploy
`./deploy.sh project-id`

##### Configuration

Configuration is stored in the `config.json` file. The file contains two arrays.

1. `tags` - A list of tags that will be applied to the resources (if the plugin impliments a function by the name _get_TAGNAME)
2. `on_demand` - A list of plugins that will tag whenever there is a new object of their type (as opposed to tagging as part of a batch command). 
Note: There is no support for CloudSQL for now)


### Local Development
For local development run:

 `dev_appserver.py --log_level=debug app.yaml`

## Extension
Iris is easily extendable to support tagging of other GCP services. You will need to create a Python file in the `/plugin` directory, implementing `register_signals`,   `def api_name`  and `methodsNames` functions as following:

All plugins are derived from `Plugin` class and need to implement the following functions:

 
Each plugin will execute will loop over all the tags that are defined in the config file and will execute the `_get_TAGNAME` function