from plugins.subscriptions import Subscriptions
from test_scripts.utils_for_tests import label_one

project = 'joshua-playground-host-vpc'
#method_name = 'Subscriber.CreateSubscription'
method_name=Subscriptions().method_names()[0]
name = 'sub1'
parent_name = 'topic1'

label_one(project, name, method_name, parent_name)
