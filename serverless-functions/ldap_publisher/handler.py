import cis_logger
import logging
import socket
import sys

import cis_publisher
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all


patch_all()


def setup_logging():
    logger = logging.getLogger()
    for h in logger.handlers:
        logger.removeHandler(h)
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(cis_logger.JsonFormatter(extra={"hostname": socket.gethostname()}))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)
    return logger


def handle(event, context={}):
    """Handle the publishing of users."""
    logger = setup_logging()
    ldap = cis_publisher.ldap.LDAPPublisher()
    if isinstance(event, list):
        ldap.publish(event)
    else:
        ldap.publish()
    return 200
