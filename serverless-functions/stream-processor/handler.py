import base64
import cis_aws
import cis_processor
import json
import logging
import sys


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
    records = event['Records']
    connection_layer = cis_aws.connect.AWS()
    connection_layer.session('us-west-2')

    dynamodb_client = connection_layer.identity_vault_client()['client']
    dynamodb_table = connection_layer.identity_vault_client()['table']

    for record in records:
        user_profile = json.loads(base64.b64decode(record['kinesis']['data']))
        user_id = user_profile['user_id']['value']
        logger.info('Record deserialized for user: {}'.format(user_id))
        record_op = cis_processor.operation.BaseProcessor(
            event_record = record,
            dynamodb_client = dynamodb_client,
            dynamodb_table = dynamodb_table
        )
        record_op._load_profiles()
        result = record_op.process()
        logger.info('Result of the operation for user: {} was: {}'.format(user_id, result))
