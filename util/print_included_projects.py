from util.config_utils import configured_projects

"""Used from deploy.sh"""


def print_included_projects():
    projects = configured_projects()
    print(" ".join(projects))


if __name__ == "__main__":
    print_included_projects()
