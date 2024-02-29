import sys

from test_scripts.integration_test.fewtype_integ_test import FewTypeIntegTest
from test_scripts.integration_test.manytype_integ_test import ManyTypeIntegTest
from test_scripts.utils_for_tests import assert_root_path

if __name__ == "__main__":
    assert_root_path()

    repeat_a_few_resource_types = "True" == sys.argv[3] if len(sys.argv) > 3 else False

    if repeat_a_few_resource_types:
        tst = FewTypeIntegTest()
    else:
        tst = ManyTypeIntegTest()

    tst.deploy_test_and_uninstall()
    print("Exit Status:", "Failure" if tst.exit_code else "Success")
    sys.exit(tst.exit_code)
