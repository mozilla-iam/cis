import logging
import os
import json


from jsonschema import validate as jsonschema_validate


logger = logging.getLogger(__name__)


CIS_SCHEMA_JSON = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../../schema.json')
with open(CIS_SCHEMA_JSON, 'r') as schema_data:
    CIS_SCHEMA = json.load(schema_data)


def run(publisher, decrypted_payload):
    # Encode binary decrypted payload to unicode string
    # Load json as dictionary object
    # Check for content validity against jsonschema
    json_object = json.loads(decrypted_payload.decode('utf-8'))
    jsonschema_validate(json_object, CIS_SCHEMA)
    return True
