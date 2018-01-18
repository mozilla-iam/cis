"""
:mod:`cis.settings` -- CIS configuration

* Environment variables used
  * CIS_ARN_MASTER_KEY
  * CIS_DYNAMODB_TABLE
  * CIS_KINESIS_STREAM_NAME
  * CIS_LAMBDA_VALIDATOR_ARN
  * CIS_PERSON_API_URL
  * CIS_PERSON_API_AUDIENCE
  * CIS_PERSON_API_VERSION
  * CIS_OAUTH2_CLIENT_ID
  * CIS_OAUTH2_CLIENT_SECRET
  * CIS_OAUTH2_DOMAIN
"""

from everett.manager import ConfigManager
from everett.manager import ConfigOSEnv


def get_config():
    return ConfigManager(
        [
            ConfigOSEnv()
        ]
    )
