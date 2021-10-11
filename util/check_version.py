import sys

"""Called from deploy.sh"""
if __name__ == "__main__":
    major_min, minor_min = 3, 8
    if not (
        sys.version_info.major == major_min and sys.version_info.minor >= minor_min
    ):
        print(
            "This script requires Python {}.{} or higher!".format(major_min, minor_min)
        )
        print(
            "You are using Python {}.{}.".format(
                sys.version_info.major, sys.version_info.minor
            )
        )
        sys.exit(1)
