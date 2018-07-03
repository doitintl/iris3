# Iris

[Blog Post](https://blog.doit-intl.com/auto-tagging-google-cloud-resources-6647cc7477c5)

In Greek mythology, Iris (/ˈaɪrɪs/; Greek: Ἶρις) is the personification of the rainbow and messenger of the gods. Iris was mostly the handmaiden to Hera.

Iris helps to automatically assign labels to Google Cloud resources for better manageability and billing reporting. Each resource in Google Cloud will get an automatically generated label in a form of [iris_name:name], [iris_region:region] and finally [iris_zone:zone]. For example if you have a Google Compute Engine instance named `webserver`, Iris will automatically label this instance with [iris_name:webserver], [iris_region:uscentral1] and [iris_zone:1f].

**Supported Google Cloud Products**

Iris is extensible through plugins and new Google Cloud products may be supported via simply adding a plugin. Right now, there are plugins for the following products:

* Google Compute Engine 
* Google Cloud Storage
* Google CloudSQL
* Google BigQuery
* Google Bigtable

##### Install dependencies

`pip install -r requirements.txt -t lib`

##### Deploy
`./deploy.sh project-id`

### Local Development
For local development run:

 `dev_appserver.py --log_level=debug app.yaml`
 
 Iris is easly extendable to support tagging of other GCP services.
 You will need to create a Python file in the /plugin directory with
 `register_signals` function as following:
 
     def register_signals(self):
 
        """ 
          Register with the plugin manager.
        """
        
        self.bigquery = discovery.build(
            'bigquery', 'v2', credentials=CREDENTIALS)
        
        logging.debug("BigQuery class created and registering signals")
 
 
You will need to create also a `def do_tag(self, project_id):` function that will do the actual work. The plugin manager will automatically load and run any code in the plugin directory which have this interface.
