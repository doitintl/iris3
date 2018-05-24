# Iris
Iris helps to automatically assign labels to Google Cloud resources for better manageability and billing reporting. Each resource in Google Cloud will get an automatically generated label in a form of [otag:name], for example if you have a Google Compute Engine instance named webserver, Iris will automatically label this instance with [otag:webserver].

**Supported Google Cloud Products**

Iris is extensible through plugins and new Google Cloud products may be supported via simply adding a plugin. Right now, there are plugins for the following products:
 - Google Compute Engine
 - Google Cloud Storage
 - Google CloudSQL
 - Google BigQuery
 - Google Bigtable
