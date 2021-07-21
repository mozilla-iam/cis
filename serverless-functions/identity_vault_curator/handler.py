
import cis_logger
import logging
import socket
import sys

from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all
from cis_identity_vault import vault


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


def handle(event=None, context={}):
    logger = setup_logging()
    logger.debug('The function is initialized.')
    v = vault.IdentityVault()
    v.connect()
    v.find_or_create()
    # XXX TBD if found.  Call create backup.  Support a backup and restore across tables.
    v.tag_vault()  # Vault tagging is critical to the service discovery layer.  Probably should raise and alert if it fails.
    v.setup_stream()
    return 200
