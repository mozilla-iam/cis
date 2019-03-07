import cis_logger
import logging
import socket
import sys

from cis_notifications import common
from cis_notifications import event as cis_event


def setup_logging():
    logger = logging.getLogger()
    for h in logger.handlers:
        logger.removeHandler(h)
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(cis_logger.JsonFormatter(extra={"hostname": socket.gethostname()}))
    logger.addHandler(h)
    logger.setLevel(logging.DEBUG)
    return logger


def handle(event, context):
    logger = setup_logging()
    config = common.get_config()

    # Subscriptions is a comma delimited string of publishers who would like to recieve notifications.
    subscriptions = config("subscriptions", namespace="cis", default="https://dinopark.k8s.sso.allizom.org/beta/")

    results = []
    for record in event.get("Records"):
        event_mapper = cis_event.Event(record, subscriptions)
        notification = event_mapper.to_notification()
        result = event_mapper.send(notification)
        results.append(result)

    logger.info("The results of the operation is: {}".format(results))
    return results
