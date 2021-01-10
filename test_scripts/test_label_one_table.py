from test_scripts.utils_for_tests import label_one

project = 'joshua-playground-host-vpc'
method_name = 'tableservice.insert'
name = 'table3'
parent_name = 'dataset3'

label_one(project, name, method_name, parent_name)
