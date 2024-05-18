# How to develop and test in this codebase

For the main documentation, see [README](./README.md).
 
## Development tools

* Prerequisites for developing and building.
    * See [INSTALL](INSTALL.md).
    * Also, for development, set up a virtual env and run `pip3 install -r requirements.txt`
* Run the server locally
    * Run `main.py` as an ordinary Flask application as follows:
        * To use the command-line,
          use `export FLASK_ENV=development;export FLASK_RUN_PORT=8000;export FLASK_DEBUG=1;FLASK_APP=main.py python -m flask run`
        * In an interactive development environment, run `main.py`, first setting these environment variables.
* For hands-on debugging
    * Use `test_do_label` and `test_label_one` and `test_schedule` to trigger against your localhost dev-server; this will label actual Cloud resources that you have pre-deployed.
        * See the `test_...` files for instructions.

## Adding new kinds of labels

Iris adds about twenty kinds of labels. More can be added, but don't add too many: Billing analytics work best when not swamped by excess labels. This is why Iris does not implement all possible labeling, say by automatically copying all fields from each resource into labels.

## Developing new labels for an existing resource type

To add a new label key to an existing resource type, add `_gcp_<LABEL_NAME>` methods (like `_gcp_zone()`) in the relevant file in `/plugins`, following the example of the existing ones. Labels will be added with a key from the function name (`zone` in that example), and a value returned by the function (in our example, the zone identifier).

For example, you might want to add a label identifying the creator of a resource, or add the name of the topic to its subscriptions.

## Supporting new resource types

Iris is easily extensible with plugins, to support labeling of other GCP resources. Use existing files in `/plugins` as examples.

1. Create a Python file in the `/plugins` directory, holding a subclass of `Plugin`.

   a. The filename and class name take the form: `cloudsql.py` and `Cloudsql`. That's lowercase and Titlecase. (Only the
   first character is capitalized, even in multiword names.) The two names should be the same except for case.

   b. Implement abstract methods from the `Plugin` class.

   c. Add `_gcp_<LABEL_NAME>` methods (like `_gcp_zone()`). Labels will be added with a key from the function
   name (`zone` in that example), and a value returned by the function
   (in our example, the zone identifier).

   d. For resources that cannot be labeled on creation (like CloudSQL, which takes too long to initialize), you should
   override `is_labeled_on_creation()` and return `False`  (though if you don't, the only bad-side effect will be errors
   in the logs).

   e. For resources with mutable labels  (like Disks, for which attachment state may have changed), override `relabel_on_cron()` and return `True`. This will allow Cloud Scheduler to relabel them. (This is because after a resource is created and possibly labeled, so Cloud Scheduler is the way to relabel mutated state.)

2. Add the relevant Google Cloud API to the `required_svcs` in `deploy.sh`.

3. Add your Google Cloud API "methods" to `log_filter` in `deploy.sh`.
    * `methodName` is part of the logs generated on creation.
    * See examples of such logs in `sample_data` directory.
        * E.g., you can see a log sample for bucket creation, in
          file `sample_data/storage.buckets.create.log_message.json`. (Or create a bucket and look at the log.)
        * In that file you see `"methodName": "storage.buckets.create"`.

4. Add permissions in `iris-custom-role.yaml` to be granted to the Iris custom role. 
   * This role allows Iris, for each resource type, to list, get, and update. 
     * ("Update" requires permission `setLabels` where available or permission `update`  otherwise.) 
     * The name of this custom role is `iris3`by default, but may be set by passing env variable `IRIS_CUSTOM_ROLE` in calling `deploy.sh` or `uninstall.sh`

# Testing

## Integration test

`./test_scripts/integration_test.py` creates a Google App Engine app and cloud resources, and tests against them. Run it without parameters for usage instructions.

# Next steps

See `TODO.md` and GitHub issues for potential future improvements.
