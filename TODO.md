# Improvements and fixes

# Note: see also Github Issues

 
* P2 Even an empty AppEngine app (not Iris, just a Hello World with 3 lines of code in total) crashes on out-of-memory for the smalled AppEngine instance. Google has confirmed this. See if there is a workaround. This will same money.

* P2 PubSub push endpoint security:
  Note: The token by itself is not very secure, though  
  Google has at times recommended this approach.

  Alternatives:
    - Replace the `PUBSUB_VERIFICATION_TOKEN` with random value in `deploy.sh`
    - Or better: [Use JWT](https://cloud.google.com/pubsub/docs/push)

* P3 Use Cloud Tasks instead of PubSub
    * to trigger `label_one`. This will allow a delay of 10 minutes for Cloud SQL, so allowing the labeling for Cloud
      SQL to happen on creation (rather than just on cron).
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

* P3 Label immediately after an event in certain cases, as opposed to using a daily cron as is now done.
    * Cloud SQL Instances
        * See above re Cloud Tasks
    * Boot disks that are created with the instance
        * This is done by pulling a list of disks from the information about the instance.
          See [GCP Auto Tag](https://github.com/doitintl/gcp-auto-tag/blob/main/main.py),
    * The attachment status of disks
        * When attachment status changes, a label needs to change from false to true or vice versa.
        * Current code does it on cron schedule.
        * We could do it on-event by capturing the log for the attachment event, just as we already capture logs for
          creation events.

* P3 Address the error *"Labels fingerprint either invalid or resource labels have changed",* printed
  in `_batch_callback`, which occurs intermittently, especially with disks. Solutions:
    - Retry
    - Ignore and let the cron do it
    - Implement Cloud Task with a delay. (Not clear if that will help.)

* P3 Rethink the need for title case in class names. This is clumsy for `Cloudsql`.

* P3 Concurrent execution
    * Init of multiple plugins is among the biggest slowdowns. They could be initialized concurrently.

* P4 Implement new labels, for example using ideas from
  the [GCP Auto Tag project](https://github.com/doitintl/gcp-auto-tag/)
  But **don't add too many**: There are *a lot* of fields on resources.
    - Add a label with the email of the creator of the resource
