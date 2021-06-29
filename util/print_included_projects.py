from util.config_utils import included_projects

"""Used from deploy.sh"""


def print_included_projects():
    projects = included_projects()
    print(" ".join(projects))


if __name__ == "__main__":
    print_included_projects()
