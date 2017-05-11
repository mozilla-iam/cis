import json
import logging
import os

from jsonschema import validate as jsonschema_validate

from cis.encryption import decrypt


CIS_SCHEMA_JSON = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'schema.json')

with open(CIS_SCHEMA_JSON, 'r') as schema_data:
    CIS_SCHEMA = json.load(schema_data)


logger = logging.getLogger(__name__)


def validate(**payload):
    """
    Validates the payload passed to CIS.

    :payload: Encrypted payload based on the output of `cis.encryption.encrypt` method
    """

    try:
        # Decrypt payload coming from CIS using KMS key
        # This ensures that publisher is trusted by CIS
        decrypted_payload = decrypt(**payload)
    except Exception:
        logger.exception('Decryption failed')
        return False

    try:
        # Encode binary decrypted payload to unicode string
        # Load json as dictionary object
        # Check for content validity against jsonschema
        json_object = json.loads(decrypted_payload.decode('utf-8'))
        jsonschema_validate(json_object, CIS_SCHEMA)
    except Exception:
        logger.exception('Jsonschema validation failed')
        return False

    return True
