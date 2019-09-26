import cis_logger
import logging
import socket
import sys

from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

from cis_postgresql import exchange
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


def handle(event, context={}):
    """Handle the publishing of users."""
    logger = setup_logging()
    v = vault.RelationalIdentityVault()
    v.find_or_create()
    exch = exchange.DynamoStream()
    user_ids = exch.user_ids_from_stream(event)
    profiles = exch.profiles(user_ids)
    postgres_vault = exchange.PostgresqlMapper()
    result = postgres_vault.to_postgres(profiles)
    logger.info(f'Profiles have been written to the vault with result: {result}')
    return 200
