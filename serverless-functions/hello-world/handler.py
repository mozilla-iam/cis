import api  # Replace with your actual application
import serverless_wsgi

serverless_wsgi.TEXT_MIME_TYPES.append("application/custom+json")

def handle(event, context):
    return serverless_wsgi.handle_request(api.app, event, context)
