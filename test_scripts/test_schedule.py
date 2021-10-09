import os
import sys

from plugins.snapshots import Snapshots
from test_scripts.utils_for_tests import label_one, do_local_http
import os

"""
This is a debugging tool  useful in development.  
 
It calls the same endpoint which would be called by Cloud Scheduler in runtime.

Run in project root.
"""
do_local_http("schedule", method="GET", headers={"X-Appengine-Cron":"true"})
