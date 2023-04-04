from test_scripts.utils_for_tests import do_local_http, assert_root_path

"""
This is a debugging tool  useful in development.  
 
It calls the same endpoint which would be called by Cloud Scheduler in runtime.

 
"""
assert_root_path()
do_local_http("schedule", method="GET", headers={"X-Appengine-Cron": "true"})
