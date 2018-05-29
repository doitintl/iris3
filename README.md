# Iris
[![License](https://img.shields.io/github/license/doitintl/iris.svg)](LICENSE) [![GitHub stars](https://img.shields.io/github/stars/doitintl/iris.svg?style=social&label=Stars&style=for-the-badge)](https://github.com/doitintl/iris)

In Greek mythology, Iris (/ˈaɪrɪs/; Greek: Ἶρις) is the personification of the rainbow and messenger of the gods. Iris was mostly the handmaiden to Hera.

Iris helps to automatically assign labels to Google Cloud resources for better manageability and billing reporting. Each resource in Google Cloud will get an automatically generated label in a form of [otag:name], for example if you have a Google Compute Engine instance named `webserver`, Iris will automatically label this instance with [otag:webserver].

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


#### Authentication
In order to allow Iris to manage instances on your behalf in any project under your organization, you will need to create a new entry in your Organization IAM and assign Iris’s service account.

First, navigate to https://console.cloud.google.com, then IAM from the menu and then select the name of your project that you deployed Iris in, from the dropdown at the top of the page:

![](iam.png)

The name of the service account you will need to assign permissions to is as following:`<YOUR_PROJECT_ID>@appspot.gserviceaccount.com` and will have been automatically created by Google App Engine. *NOTE:* this is done under *IAM*, selecting the account, choosing *Permissions* and then adding the following roles to it; not under *Service Accounts*.

*  **BigQuery Admin**
*  **Bigtable Administrator**
*  **Cloud SQL Admin**
*  **Compute Admin**
*  **Storage Admin** 

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
 
