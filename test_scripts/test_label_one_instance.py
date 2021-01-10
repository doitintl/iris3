from test_scripts.utils_for_tests import label_one

method_name = 'compute.instances.insert'
project = 'joshua-playground-host-vpc'
name = 'instance-small'

label_one(project, name, method_name)
