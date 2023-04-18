from test_scripts.utils_for_tests import do_local_http, assert_root_path
from util.utils import init_logging

"""
This is a debugging tool used in development.  
 
It calls the same endpoint which would be called by Cloud Scheduler in runtime.
"""

init_logging()
assert_root_path()
do_local_http("schedule", method="GET", headers={"X-Appengine-Cron": "true"})
