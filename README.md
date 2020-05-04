# Iris

[Blog Post](https://blog.doit-intl.com/auto-tagging-google-cloud-resources-6647cc7477c5)

In Greek mythology, Iris (/ˈaɪrɪs/; Greek: Ἶρις) is the personification of the rainbow and messenger of the gods. Iris was mostly the handmaiden to Hera.

Iris helps to automatically assign labels to Google Cloud resources for better manageability and billing reporting. Each resource in Google Cloud will get an automatically generated label in a form of [iris_name:name], [iris_region:region] and finally [iris_zone:zone]. For example if you have a Google Compute Engine instance named `nginx`, Iris will automatically label this instance with [iris_name:nginx], [iris_region:us-central1] and [iris_zone:us-central1-a].

Iris will also label short lived Google Compute Engine instances such as preemtible instances or instances managed by Instance Group Manager by listening to Stackdriver Logs and putting required labels on-demand.

**NOTE**: Iris will try tagging resources in _all_ project across your GCP organization. Not just the project it will be deployed into.

## Supported Google Cloud Products

Iris is extensible through plugins and new Google Cloud products may be supported via simply adding a plugin. Right now, there are plugins for the following products:

* Google Compute Engine (including disks and snapshots)
* Google Cloud Storage
* Google BigQuery
* Google Bigtable

## Installation

We recommend to deploy Iris in a [separate](https://cloud.google.com/resource-manager/docs/creating-managing-projects#creating_a_project) project within your Google Cloud organization.
To deploy, you will need to have *Owner* role on Iris project and the following roles in your *GCP Organization*:

 * _Organization Role Administrator_ - to create a custom IAM role for Iris that allows setting labels on the services
   (note this is different from _Organization Administrator_, which is in turn not related to Organization-level _Owner_)
 * _Security Admin* OR *Organization Administrator* - to allow Iris app engine service account to use the above role
 * _Logs Configuration Writer_ OR _Logs Configuration Writer_ - to configure log events stream on Organization level to watch for new instances, databases, etc.

### Install dependencies

```
pip2.7 install -r requirements.txt -t lib
```

Yes, we still use Python2.7. Yes, [we know](https://pythonclock.org/).

#### Deploy

```
./deploy.sh <project-id>
```

#### Configuration

Configuration is stored in the config.json file. The file contains two arrays.

1. tags - A list of tags that will be applied to the resources (if the corresponding plugin implemented a function `_get_<TAGNAME>()`)
2. on_demand - A List of plugins that will tag whenever a new object of their type is created

```json
{
  "tags": [
    "name",
    "zone",
    "region",
    "location",
    "instance_type"
  ],
  "on_demand": [
    "Gce",
    "BigQuery",
    "Gcs",
    "BigTable",
    "GceDisks",
    "GceSnapshots"
  ]
}
```

### Local Development
For local development run:

 `dev_appserver.py --log_level=debug app.yaml`

Iris is easily extendable to support tagging of other GCP services. You will need to create a Python file in the /plugin directory with `register_signals`,   `def api_name`  and `methodsNames` functions as following:

```python
     def register_signals(self):

        """
          Register with the plugin manager.
        """

        logging.debug("BigQuery class created and registering signals")
```

```python
 def api_name(self):
        return "compute.googleapis.com"
```

```python
	// a list of log methods to listen on
    def methodsNames(self):
        return ["storage.buckets.create"]
```

All plugins are derived form `Plugin` class and needs to implement the following functions:

1. `do_tag(self, project_id)`
1. `get_gcp_object(self, data)`
1. `tag_one(self, gcp_object, project_id)`
1. `api_name(self)`
1. `methodsNames(self)`


Each plugin will execute `gen_labels()` which will loop over all the tags that are defined in the config file and will execute `_get_<TAGNAME>()` function
