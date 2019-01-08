import boto3
import logging
import os
from botocore.stub import Stubber
from everett.manager import ConfigManager
from everett.manager import ConfigIniEnv
from everett.manager import ConfigOSEnv
from json import dumps


logger = logging.getLogger(__name__)


def get_config():
    return ConfigManager(
        [
            ConfigIniEnv([
                os.environ.get('CIS_CONFIG_INI'),
                '~/.mozilla-hris_api.ini',
                '/etc/mozilla-hris_api.ini'
            ]),
            ConfigOSEnv()
        ]
    )


config = get_config()


def session():
    region = config('region_name', namespace='hris_api', default='us-west-2')
    if config('environment', namespace='hris_api', default='local') == 'local':
        boto_session = Stubber(boto3.session.Session(region_name=region)).client
    else:
        boto_session = boto3.session.Session(region_name=region)
    return boto_session


def connect():
    boto_session = session()
    if config('environment', namespace='hris_api', default='local') == 'local':
        dynalite_port = config('dynalite_port', namespace='hris_api', default='4567')
        dynalite_host = config('dynalite_host', namespace='hris_api', default='localhost')
        dynamodb_client = boto_session.client(
            'dynamodb', endpoint_url='http://{}:{}'.format(
                dynalite_host,
                dynalite_port
            )
        )
    else:
        dynamodb_client = boto_session.client('dynamodb')
    return dynamodb_client


def create(dynamodb_client):
    environment = config('environment', namespace='hris_api', default='local')
    result = dynamodb_client.create_table(
        TableName='hris-api-{}'.format(environment),
        KeySchema=[
            {'AttributeName': 'primary_email', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'primary_email', 'AttributeType': 'S'}
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5
        }
    )

    waiter = dynamodb_client.get_waiter('table_exists')
    waiter.wait(
        TableName='hris-api-{}'.format(
            config('environment', namespace='hris_api', default='local')
        ),
        WaiterConfig={
            'Delay': 30,
            'MaxAttempts': 5
        }
    )

    return result


def get_table_resource():
    region = config('dynamodb_region', namespace='hris_api', default='us-west-2')
    environment = config('environment', namespace='hris_api', default='local')
    table_name = 'hris-api-{}'.format(environment)

    if environment == 'local':
        dynalite_host = config('dynalite_host', namespace='hris_api', default='localhost')
        dynalite_port = config('dynalite_port', namespace='hris_api', default='4567')
        session = Stubber(boto3.session.Session(region_name=region)).client
        resource = session.resource(
            'dynamodb',
            endpoint_url='http://{}:{}'.format(
                dynalite_host,
                dynalite_port
            )
        )
    else:
        session = boto3.session.Session(region_name=region)
        resource = session.resource('dynamodb')

    table = resource.Table(table_name)
    return table


def find(dynamodb_client):
    try:
        if config('environment', namespace='hris_api', default='local') == 'local':
            return dynamodb_client.describe_table(TableName='hris-api-local')['Table']['TableArn']
        else:
            # Assume that we are in AWS and list tables, describe tables, and check tags.
            tables = self.dynamodb_client.list_tables(
                Limit=100
            )

            for table in tables.get('TableNames'):
                table_arn = self.dynamodb_client.describe_table(TableName=table)['Table']['TableArn']
                if table == 'hris-api-{}'.format(
                    config('environment', namespace='hris_api', default='local') == 'local'
                ):
                    return table_arn
    except Exception as e:
        logger.error('Could not locate table.')
        return None


def find_or_create():
    dynamodb_client = connect()
    if find(dynamodb_client) is not None:
        table = get_table_resource()
    else:
        create(dynamodb_client)
        table = get_table_resource()
    return table
