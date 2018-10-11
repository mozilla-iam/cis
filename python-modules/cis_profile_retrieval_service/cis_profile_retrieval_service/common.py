import boto3
import os
from botocore.stub import Stubber
from everett.manager import ConfigManager
from everett.manager import ConfigIniEnv
from everett.manager import ConfigOSEnv
from json import dumps
from iam_profile_faker.factory import V2ProfileFactory
from cis_identity_vault.models import user
from cis_identity_vault.vault import IdentityVault


def get_config():
    return ConfigManager(
        [
            ConfigIniEnv([
                os.environ.get('CIS_CONFIG_INI'),
                '~/.mozilla-cis.ini',
                '/etc/mozilla-cis.ini'
            ]),
            ConfigOSEnv()
        ]
    )


config = get_config()


def get_table_resource():
    region = config('dynamodb_region', namespace='cis', default='us-west-2')
    environment = config('environment', namespace='cis', default='local')
    table_name = '{}-identity-vault'.format(environment)

    if environment == 'local':
        dynalite_host = config('dynalite_host', namespace='cis', default='localhost')
        dynalite_port = config('dynalite_port', namespace='cis', default='4567')
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


def initialize_vault():
    if config('environment', namespace='cis', default='local') == 'local':
        identity_vault = IdentityVault()
        identity_vault.find_or_create()
    else:
        return None


def seed(number_of_fake_users=100):
    seed_data = config('seed_api_data', namespace='cis', default='false')
    if seed_data.lower() == 'true':
        table = get_table_resource()
        user_profile = user.Profile(table)

        if len(user_profile.all) > 0:
            pass
        else:
            factory = V2ProfileFactory()
            factory.create()
            identities = factory.create_batch(number_of_fake_users)

            for identity in identities:
                identity_vault_data_structure = {
                    'id': identity.get('user_id').get('value'),
                    'primary_email': identity.get('primary_email').get('value'),
                    'sequence_number': '1234567890',
                    'profile': dumps(identity)
                }

                user_profile.create(identity_vault_data_structure)
