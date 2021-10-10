from test_scripts.utils_for_tests import do_local_http

"""
This is a debugging tool  useful in development.  
 
It calls the same endpoint which would be called by Cloud Scheduler in runtime.

Run in project root.
"""
do_local_http("schedule", method="GET", headers={"X-Appengine-Cron": "true"})
