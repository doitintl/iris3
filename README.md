# Iris

[Blog Post](https://blog.doit-intl.com/auto-tagging-google-cloud-resources-6647cc7477c5)

In Greek mythology, Iris (/ˈaɪrɪs/; Greek: Ἶρις) is the personification of the rainbow and messenger of the gods. Iris was mostly the handmaiden to Hera.

Iris helps to automatically assign labels to Google Cloud resources for better manageability and billing reporting. Each resource in Google Cloud will get an automatically generated label in a form of [iris_name:name], [iris_region:region] and finally [iris_zone:zone]. For example if you have a Google Compute Engine instance named `nginx`, Iris will automatically label this instance with [iris_name:nginx], [iris_region:us-central1] and [iris_zone:us-central1-a].

Iris will also label short lived Google Compute Engine instances such as preemtible instances or instances managed by Instance Group Manager by listening to Stackdriver Logs and putting required labels on-demand. 

**Supported Google Cloud Products**

Iris is extensible through plugins and new Google Cloud products may be supported via simply adding a plugin. Right now, there are plugins for the following products:

* Google Compute Engine (including disks and snapshots)
* Google Cloud Storage
* Google CloudSQL
* Google BigQuery
* Google Bigtable

**Installation**

We recommend to deploy Iris in a [new project](https://cloud.google.com/resource-manager/docs/creating-managing-projects#creating_a_project) within your Google Cloud organization. You will need the following IAM permissions on your Google Cloud organization to complete the deployment: 

 * App Engine Admin
 * Logs Configuration Writer
 * Pub/Sub Admin

##### Install dependencies

`pip install -r requirements.txt -t lib`

##### Deploy
`./deploy.sh project-id`

##### Configuration

Configuration is stored in the config.json file. The file contais two arrays.

1. tags - A list of tgas that will be applide to the resources (if the plugin implimented a function by the name _get_TAGNAME)
2. on_demand - A List of plugins that will tag whenever there is a new object of their type (No support for CloudSQL for now)

```{
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
 
Iris is easly extendable to support tagging of other GCP services. You will need to create a Python file in the /plugin directory with `register_signals`,   `def api_name`  and `methodsNames` functions as following:

```
     def register_signals(self):
 
        """ 
          Register with the plugin manager.
        """
         
        logging.debug("BigQuery class created and registering signals")
```

```
 def api_name(self):
        return "compute.googleapis.com"
```


```
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

 
Each plugin will execute `gen_labels` which will loop over all the tags that are defined in the config file and will execute _get_TAGNAME function