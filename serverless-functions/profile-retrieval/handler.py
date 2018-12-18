import cis_profile_retrieval_service
import logging
import serverless_wsgi
import sys


serverless_wsgi.TEXT_MIME_TYPES.append("application/custom+json")


def setup_logging():
    logger = logging.getLogger()
    for h in logger.handlers:
        logger.removeHandler(h)
    h = logging.StreamHandler(sys.stdout)
    FORMAT = '%(message)s'
    h.setFormatter(logging.Formatter(FORMAT))
    logger.addHandler(h)
    logger.setLevel(logging.DEBUG)
    return logger


def handle(event, context):
    logger = setup_logging()
    return serverless_wsgi.handle_request(cis_profile_retrieval_service.v2_api.app, event, context)
