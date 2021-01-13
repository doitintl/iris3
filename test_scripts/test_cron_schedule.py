from test_scripts.utils_for_tests import do_local_http

# 'X-Appengine-Cron'  need to get through 'authentication; for /schedule endpoint in localhost.
# However, in GAE, the header is stripped out by GAE; only  GAE is allowed to add this header.
do_local_http("schedule", None, "GET", headers={"X-Appengine-Cron": "true"})
