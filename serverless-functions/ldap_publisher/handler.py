import cis_logger
import logging
import socket
import sys

import cis_publisher


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
    logger = setup_logging()

    # Do stuff with cis_publisher for ldap publishing here.
    pass