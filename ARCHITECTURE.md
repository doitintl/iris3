# Architecture

For the main documentation, See [README](./README.md).

## Iris' architecture
* Iris runs in Google App Engine Standard Environment (Python 3).
* It has Organization-level and project-level elements
  * Note that Iris's design makes it focused on labeling resources across an  organization.
  * You can filter using the config file, so that Iris labels only some of the   projects in an org 
  * Iris has architecture components which are deployed to  the org, and others which are deployed to  the project.
  * If you want a person with all permissions to deploy the org-level elements and a person without org-level permissions to redeploy only the project-level elements (e.g. when you change configuration), you can split the deployment in this way  with flags on the script. Run `deploy.sh -h`.
* The Cloud Scheduler "cron" job triggers Iris at configured intervals. See `cron_full.yaml` for config. The GCP Console view for this is in a separate App Engine tab in the Cloud Scheduler view.
* For newly created resources, a Log Sink on the organization level sends all logs for resource creation to a PubSub topic.
    * The Log Sink is filtered to include only supported resource types.
    * If you edit the configuration file so that only specific projects are to be labeled, the Log Sink only captures these.
* PubSub topics:
*  

iris_deadletter_topic	 
    * `iris_logs_topic`  receives the resource-creation logs from the Log Sink
    * `iris_schedulelabeling_topic`  receives messages sent by the `/schedule` endpoint in `main.py` (after the `/schedule` endpoint was triggered by the Cloud Scheduler). Each message goes to endpoint `/do_label` to trigger the labeling of a given resource type in a given project.
    * Messages to `iris_label_all_types_topic` triggers the labeling of all resources regardless of type.
    * Another topic is a dead-letter topic.
* PubSub subscriptions
    * There are subscriptions that that  direct the messages to  endpoints  in `main.py`: `/label_one`, `/do_label` and `label_all_types`.
    * For security, the endpoints hit by these PubSub subscriptions [use JWT auth](https://cloud.google.com/pubsub/docs/authenticate-push-subscriptions), where the JWT token is verified in the Iris webapp.
    * A dead-letter subscription. This is a pull subscription. By default, it just accumulates the messages. You can use it to see statistics, or you can pull messages from it.

# Development and Testing
Please see [HACKING](./HACKING.md).
 