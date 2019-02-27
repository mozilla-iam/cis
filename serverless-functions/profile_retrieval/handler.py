import cis_logger
import logging
import cis_profile_retrieval_service
import serverless_wsgi
import socket
import sys

from aws_xray_sdk.core import xray_recorder, patch_all
from aws_xray_sdk.core.context import Context
from aws_xray_sdk.ext.flask.middleware import XRayMiddleware

serverless_wsgi.TEXT_MIME_TYPES.append("application/custom+json")

xray_recorder.configure(context_missing='LOG_ERROR')
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


def handle(event, context):
    logger = setup_logging()
    logger.debug("Profile retrieval service Initialized.")
    app = cis_profile_retrieval_service.v2_api.app
    return serverless_wsgi.handle_request(app, event, context)
