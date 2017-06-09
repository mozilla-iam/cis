"""
:mod:`cis.settings` -- CIS configuration

* Environment variables used
  * CIS_ARN_MASTER_KEY
  * CIS_DYNAMODB_TABLE
  * CIS_KINESIS_STREAM_ARN
  * CIS_LAMBDA_VALIDATOR_ARN

"""

from everett.manager import ConfigManager, ConfigOSEnv


def get_config():
    return ConfigManager(
        [
            ConfigOSEnv()
        ]
    )
