import logging

import json

logger = logging.getLogger(__name__)


def run(publisher, decrypted_payload):
    json_object = json.loads(decrypted_payload.decode('utf-8'))
    return True
