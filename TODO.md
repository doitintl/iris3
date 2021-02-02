# Improvements and fixes to be done

* Add an option to work without event-based labeling. (This saves money.)
* Implement good ideas from the [GCP Auto Tag project](https://github.com/doitintl/gcp-auto-tag/)
    - Add a label with the email of the creator of the resource
    - For disks, add a label with the name of the instance to which 
    they are attached.
    - Immediately label boot disks that are created with their instance. 
        * (This seems not to work now in Iris3, though that needs to be double-checked.)
        * As shown in [GCP Auto Tag](https://github.com/doitintl/gcp-auto-tag/blob/main/main.py), do this by pulling a list of
        disks from the information about the instance.
* In `integration_test.sh`
    - Test more labels (in addition to `iris3_name`)
    - Test the copying of project labels.
* Test CloudSQL automatically (difficult because it takes 10 minutes to initialize)
* PubSub push endpoint security:
  Note: This token is not very secure, though it is an improvement on earlier versions of Iris,
  and Google has at times recommended it.

  Either
    - Replace the `PUBSUB_VERIFICATION_TOKEN` with random value in `deploy.sh`
    - Or better: [Use JWT](https://cloud.google.com/pubsub/docs/push)
* Use Cloud Tasks instead of PubSub to trigger `label_one`. This will allow a delay of ~10 minutes, which should
  allow the labeling on creation of Cloud SQL Instances, and maybe boot disks created with VM instances.
* Address the error *"Labels fingerprint either invalid or resource labels have changed",* printed in `_batch_callback`,
  which occurs intermittently, especially with disks.
    Solutions:
      - Retry
      - Ignore and let the cron do it
      - Implement Cloud Task with a delay. (Not clear if that will help.)
* Rethink the need for title case, which is clumsy for `Bigtable` and `Cloudsql`.