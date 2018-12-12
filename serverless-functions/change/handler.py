import cis_change_service
import logging
import serverless_wsgi

FORMAT = '%(asctime)-15s %(clientip)s %(user)-8s %(message)s'
logging.basicConfig(level=logging.DEBUG, format=FORMAT)

serverless_wsgi.TEXT_MIME_TYPES.append("application/custom+json")

def handle(event, context):
    return serverless_wsgi.handle_request(cis_change_service.api.app, event, context)
