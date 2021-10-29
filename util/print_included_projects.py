from util.config_utils import enabled_projects

"""Used from deploy.sh"""


def print_included_projects():
    projects = enabled_projects()
    print(" ".join(projects))


if __name__ == "__main__":
    print_included_projects()
