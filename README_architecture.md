# Architecture

## For the main documentation
See [README](./README.md).

## Iris' architecture
* Iris runs in Google App Engine Standard Environment (Python 3).
* Organization-level and project-level elements
  * First, note that Iris is an organization-level application.
  * A single instance of Iris in one project labels all projects in an org (unless you limit it by configuration). 
  * Iris has architecture elements which are deployed to both the org and the project.
  * If you want a person with all permissions to deploy the org-level elements and a person without org-level permissions to redeploy only the project-level elements (e.g. when you change configuration), you can do this with flags on the script. Run `deploy.sh -h`.
* The Cloud Scheduler "cron" job triggers Iris at configured intervals. See `cron_full.yaml` for config. The GCP Console view for this is in a separate App Engine tab in the Cloud Scheduler view.
* For newly created resources, a Log Sink on the organization level sends all logs for resource creation to a PubSub topic.
    * The Log Sink is filtered to include only supported resource types
    * If you edit the configuration file so that only specific projects are to be labeled, the Log Sink only captures these.
* PubSub topics:
    * One topic receives the resource-creation logs from the Log Sink
    * Another topic receives messages sent by the `/schedule` Cloud Scheduler handler in `main.py`. (The `/schedule` path is triggered by the Cloud Scheduler). This then sends out messages, where each one triggers the labeling of a given resource tyope in a given project.
    * Another topic is a dead-letter topic.
* PubSub subscriptions
    * There is one for each topic: These direct the messages to `/label_one` and `/do_label` in `main.py`, respectively.
    * For security, these two PubSub subscriptions [use JWT auth](https://cloud.google.com/pubsub/docs/authenticate-push-subscriptions), where the JWT token is verified in the Iris webapp.
    * A dead-letter subscription. This is a pull subscription. By default, it just accumulates the messages. You can use it to see statistics, or you can pull messages from it.

# Development and Testing
Please see [HACKING](./HACKING.md)
 