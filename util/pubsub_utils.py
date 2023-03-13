import logging

from google.cloud import pubsub_v1

from util import gcp_utils, utils

__publisher = pubsub_v1.PublisherClient()


def logs_topic() -> str:
    return f"iris_logs_topic"


def schedulelabeling_topic() -> str:
    return f"iris_schedulelabeling_topic"


def publish(msg: str, topic_id: str):
    topic_path = __publisher.topic_path(gcp_utils.current_project_id(), topic_id)

    def on_publish(f):
        try:
            result = f.result()
            try:
                int(result)  # Int results indicate success, no need to log
            except ValueError:  # not an int, failed
                logging.info("PubSub publishing result %s", result)
        except Exception as e:
            logging.exception(e)

    future = __publisher.publish(topic_path, msg.encode("utf-8"))
    future.add_done_callback(on_publish)

    logging.info("Published to %s: %s", topic_id, utils.shorten(msg, 200))
