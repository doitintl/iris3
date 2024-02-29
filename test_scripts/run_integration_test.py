import sys

from test_scripts.manytype_integ_test import ManyTypeIntegTest
from test_scripts.utils_for_tests import assert_root_path

if __name__ == "__main__":
    assert_root_path()

    repeat_a_few_resource_types = bool(sys.argv[4]) if len(sys.argv) > 4 else False

    if repeat_a_few_resource_types:
        assert False
    else:
        tst = ManyTypeIntegTest()
        tst.deploy_test_and_uninstall()
        exit_code = tst.exit_code

    print("Exit Status:", "Failure" if exit_code else "Success")
    sys.exit(exit_code)
