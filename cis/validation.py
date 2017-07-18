import boto3
import logging
import os

from pluginbase import PluginBase
from cis.encryption import decrypt
from cis.settings import get_config


plugin_base = PluginBase(package='cis.plugins.validation')
plugin_source = plugin_base.make_plugin_source(searchpath=[
    os.path.join(os.path.abspath(os.path.dirname(__file__)),
    'plugins/validation/')])

# List of plugins to load, in order
plugin_load = ['json_schema_plugin']


dynamodb = boto3.resource('dynamodb')
config = get_config()
dynamodb_table = config('dynamodb_table', namespace='cis')
table = dynamodb.Table(dynamodb_table)

logger = logging.getLogger(__name__)


def validate(publisher, **payload):
    """
    Validates the payload passed to CIS.

    :payload: Encrypted payload based on the output of `cis.encryption.encrypt` method
    """

    logger.info("Attempting payload validation for publisher {}".format(publisher))

    if not publisher:
        logger.exception('No publisher provided')
        return False

    try:
        # Decrypt payload coming from CIS using KMS key
        # This ensures that publisher is trusted by CIS
        decrypted_payload = decrypt(**payload)
    except Exception:
        logger.exception('Decryption failed')
        return False

    with plugin_source:
        for plugin in plugin_load:
            cur_plugin = plugin_source.load_plugin(plugin)
            try:
                cur_plugin.run(publisher, decrypted_payload)
            except Exception:
                logger.exception('Validation plugin {} failed'.format(cur_plugin.__name__))
                return False

    return True


def retrieve_from_vault(user):
    """
    Check if a user exist in dynamodb

    :user: User's id
    """

    user_key = {'user_id': user}

    try:
        response = table.get_item(Key=user_key)
    except Exception:
        logger.exception('DynamoDB GET failed')
        return None
    return response


def store_to_vault(data):
    """
    Store data to DynamoDB.

    :data: Data to store in the database
    """

    # Put data to DynamoDB
    try:
        response = table.put_item(
            Item=data
        )
    except Exception:
        logger.exception('DynamoDB PUT failed')
        return None
    return response
