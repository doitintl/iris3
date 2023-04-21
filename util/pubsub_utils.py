import logging
from functools import lru_cache

from util import gcp_utils, utils
from util.gcp_utils import add_loaded_lib


@lru_cache(maxsize=1)
def __get_publisher():
    # This is not fully thread-safe, but at worst we get multiple PublisherClients, which are stateless
    #
    # Local import to avoid burdening AppEngine memory.
    # Loading all Cloud Client libraries would be 100MB  means that
    # the default AppEngine Instance crashes on out-of-memory even before actually serving a request.
    from google.cloud import pubsub_v1

    add_loaded_lib("pubsub_v1")
    return pubsub_v1.PublisherClient()


def logs_topic() -> str:
    return f"iris_logs_topic"


def schedulelabeling_topic() -> str:
    return f"iris_schedulelabeling_topic"


def publish(msg: str, topic_id: str):
    topic_path = __get_publisher().topic_path(gcp_utils.current_project_id(), topic_id)

    def on_publish(f):
        try:
            result = f.result()
            try:
                int(result)  # Int results indicate success, no need to log
            except ValueError:  # not an int, failed
                logging.info("PubSub publishing result %s", result)
        except Exception:
            logging.exception("")

    future = __get_publisher().publish(topic_path, msg.encode("utf-8"))
    future.add_done_callback(on_publish)

    logging.info("Published to %s: %s", topic_id, utils.shorten(msg, 200))
