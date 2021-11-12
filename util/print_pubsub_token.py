from util.config_utils import pubsub_token

"""Used from deploy.sh"""


def print_pubsub_token():
    token = pubsub_token()
    print(token)


if __name__ == "__main__":
    print_pubsub_token()
