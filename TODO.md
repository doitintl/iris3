# Improvements and fixes

## Note: see also Github Issues

* P2 Memory consumption: Even an empty AppEngine app (not Iris, just a Hello World with 3 lines of code in total) crashes on out-of-memory for the smalled AppEngine instance. Google has confirmed this. See if there is a workaround.  This will save money.

* P3 Label immediately after an event in certain cases, as opposed to using a daily cron as is now done.
    * Cloud SQL Instances
        * See above re Cloud Tasks
    * Boot disks that are created with the instance
        * This is done by pulling a list of disks from the information about the instance.
          See [GCP Auto Tag](https://github.com/doitintl/gcp-auto-tag/blob/main/main.py),
    * The attachment status of disks
        * When attachment status changes, a label needs to change from false to true or vice versa.
        * Current code does it on cron schedule.
        * We could do it on-event by capturing the log for the attachment event, just as we already capture logs for creation events.

* P3 Address the error *"Labels fingerprint either invalid or resource labels have changed",* printed
  in `_batch_callback`, which occurs intermittently, especially with disks. Solutions:
    - Retry
    - Ignore and let the cron do it
    - Implement Cloud Task with a delay. (Not clear if that will help.)

* P3 Rethink the need for title case in class names. This is clumsy for `Cloudsql`.

* P4 Implement new labels, for example using ideas from
  the [GCP Auto Tag project](https://github.com/doitintl/gcp-auto-tag/)
  But **don't add too many**: There are *a lot* of fields on resources.
    - Add a label with the email of the creator of the resource
