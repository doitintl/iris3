# Improvements and fixes to be done

* P2 Concurrent execution
    * Since all activity is highly network-constrained, it would speed up significantly with  concurrent execution
    using Python's `async`.

* P2 Labeling GKE Nodes (VM Instances) and Disks
    * Today, this is not done because it forces recreation of resources.
    * It can be done through specific mechanisms for GKE clusters.

* P2 PubSub push endpoint security:
  Note: The token which is now used is not very secure, though it is an improvement on earlier versions of Iris, and
  Google has at times recommended this approach.

  Alternatives:
    - Replace the `PUBSUB_VERIFICATION_TOKEN` with random value in `deploy.sh`
    - Or better: [Use JWT](https://cloud.google.com/pubsub/docs/push)

* P2 Use Cloud Tasks instead of PubSub
    * to trigger `label_one`. This will allow a delay of 10 minutes for Cloud SQL, so allowing the labeling to happen on
      creation (rather than just cron) for Cloud SQL
    * to trigger `do_label` from `schedule()`, with a random delay, so minimizing the number of App Engine instances
      that are created.

* P3 In `integration_test.sh`
    - Test more labels (in addition to `iris3_name` which is now tested)
    - Test the copying of labels from the project.
    - Support testing of the cron-based labeling, which would also allow testing of Cloud SQL and of attachment of
      Disks. In this test:
        1. Modify cron to run 1 minute after the deployment is launched (and restore it at the end of the test.)
        1. Call `deploy.sh` using with the `-c` switch to disable event-based labeling 1. Wait 1.5 minutes after deploy
           before checking that the labels are there

* P3 Label ASAP after it happens, rather than waiting for the cron job
    * Cloud SQL Instances 
        * See above re Cloud Tasks
    * Boot disks that are created with the instance
        * As shown in [GCP Auto Tag](https://github.com/doitintl/gcp-auto-tag/blob/main/main.py), do this by pulling a
          list of disks from the information about the instance.
    * The attachment status of disks 
        * So a label need to change from false to true or vice versa
        * This could probably be done by capturing the log for the attachment event, just as we already capture logs for creation events.

* P3 Address the error *"Labels fingerprint either invalid or resource labels have changed",* printed
  in `_batch_callback`, which occurs intermittently, especially with disks. Solutions:
    - Retry - Ignore and let the cron do it - Implement Cloud Task with a delay. (Not clear if that will help.)

* P3 Rethink the need for title case in class names. This is clumsy for `Bigtable` and `Cloudsql`.

* P4 Implement new labels, for example using ideas from
  the [GCP Auto Tag project](https://github.com/doitintl/gcp-auto-tag/)
  But **don't add too many**: There are *a lot* of fields on resources.
    - Add a label with the email of the creator of the resource
    
* P4 Move PUBSUB_VERIFICATION_TOKEN out of  `app.yaml` and into `config.yaml`. There is
  no reason that application configuration should be in two places.