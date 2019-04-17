import base64
import cis_logger
import logging
import socket
import sys
import lzma

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
    lzc = lzma.LZMACompressor()
    hris = cis_publisher.hris.HRISPublisher(context=context)
    if isinstance(event, list):
        hris.publish(user_ids=event)
    elif isinstance(event, dict):
        hris.publish(user_ids=event.get("user_ids"), cache=event.get("cache"))
    elif isinstance(event, str):
        tmp = base64.decodestring(event.decode("utf-8"))
        tmp = json.loads(lzc.decompress(tmp))
        hris.publish(user_ids=tmp.get("user_ids"), cache=tmp.get("cache"))
    else:
        hris.publish()
    return 200
