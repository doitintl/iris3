import sys

from test_scripts.integration_test.gce_integ_test import GCEIntegTest
from test_scripts.integration_test.manytype_integ_test import ManyTypeIntegTest
from test_scripts.integration_test.pubsub_integ_test import PubSubIntegTest
from test_scripts.utils_for_tests import assert_root_path

if __name__ == "__main__":
    assert_root_path()
    if len(sys.argv) > 3:
        clsname_base = sys.argv[3]
    else:
        clsname_base = "ManyType"

    if clsname_base == "ManyType":
        test = ManyTypeIntegTest()
    elif clsname_base == "GCE":
        test = GCEIntegTest()
    elif clsname_base == "GCE":
        test = PubSubIntegTest()
    else:
        raise Exception("No class " + clsname_base + " known")
    print("Test " + type(test).__name__)
    test.deploy_test_and_uninstall()
    print("Exit Status:", "Failure" if test.exit_code else "Success")
    sys.exit(test.exit_code)
