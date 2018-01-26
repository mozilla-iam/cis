import json
import logging
import os

from cis.libs import utils
from jsonschema import validate as jsonschema_validate

utils.StructuredLogger(name=__name__, level=logging.INFO)
logger = logging.getLogger(__name__)


cis_schema_json = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'schema.json')
with open(cis_schema_json, 'r') as schema_data:
    cis_schema = json.load(schema_data)


def run(publisher, vault_json, profile_json):
    # Check for content validity against jsonschema
    jsonschema_validate(profile_json, cis_schema)
