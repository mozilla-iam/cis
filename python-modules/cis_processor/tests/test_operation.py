import base64
import boto3
import json
import logging
import os
import random

from botocore.stub import Stubber
from cis_profile import profile
from cis_profile import fake_profile
from everett.ext.inifile import ConfigIniEnv
from everett.manager import ConfigManager
from everett.manager import ConfigOSEnv
from moto import mock_dynamodb2
from mock import patch

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
    datefmt='%m-%d %H:%M'
)

# define a Handler which writes INFO messages or higher to the sys.stderr
console = logging.StreamHandler()
console.setLevel(logging.INFO)


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


def profile_to_vault_structure(user_profile):
    return {
        'sequence_number': str(random.randint(100000, 100000000)),
        'primary_email': user_profile['primary_email']['value'],
        'profile': json.dumps(user_profile),
        'uuid': user_profile['uuid']['value'],
        'id': user_profile['user_id']['value']
    }


def kinesis_event_generate(user_profile):
    fh = open('tests/fixture/kinesis-event.json')
    kinesis_event_structure = json.loads(fh.read())
    fh.close()
    kinesis_event_structure['Records'][0]['kinesis']['sequenceNumber'] = '900000000000'
    kinesis_event_structure['Records'][0]['kinesis']['parititionKey'] = 'generic_publisher'
    kinesis_event_structure['Records'][0]['kinesis']['data'] = base64.b64encode(
        json.dumps(user_profile).encode()
    ).decode()

    return kinesis_event_structure


@mock_dynamodb2
class TestOperation(object):
    def setup(self):
        os.environ['CIS_CONFIG_INI'] = 'tests/fixture/mozilla-cis.ini'
        self.config = get_config()
        from cis_fake_well_known import well_known
        from cis_identity_vault import vault
        os.environ['CIS_CONFIG_INI'] = 'tests/fixture/mozilla-cis.ini'
        self.well_known_json = well_known.MozillaIAM()
        self.well_known_json.randomize_publishers = False
        self.well_known_json.publisher_keys = self.well_known_json._load_publisher_keys()

        self.dynamodb_client = boto3.client(
            'dynamodb',
            region_name='us-west-2',
            aws_access_key_id="ak",
            aws_secret_access_key="sk"
        )

        self.dynamodb_resource = boto3.resource(
            'dynamodb',
            region_name='us-west-2',
            aws_access_key_id="ak",
            aws_secret_access_key="sk"
        )

        self.vault_client = vault.IdentityVault()
        self.vault_client.boto_session = Stubber(boto3.session.Session(region_name='us-west-2')).client
        self.vault_client.dynamodb_client = self.dynamodb_client
        self.vault_client.find_or_create()
        self.table = self.dynamodb_resource.Table('testing-identity-vault')
        self.mr_mozilla_profile = fake_profile.FakeUser(generator=1337).as_dict()

        from cis_identity_vault.models import user
        vault_interface = user.Profile(self.table)
        vault_interface.create(profile_to_vault_structure(user_profile=self.mr_mozilla_profile))
        self.mr_mozilla_change_event = kinesis_event_generate(self.mr_mozilla_profile)

    def test_base_operation_object_it_should_succeed_and_skip_integration(self):
        os.environ['CIS_PROCESSOR_VERIFY_SIGNATURES'] = 'False'
        kinesis_event = kinesis_event_generate(self.mr_mozilla_profile)

        from cis_processor import operation
        for kinesis_record in kinesis_event['Records']:
            base_operation = operation.BaseProcessor(
                event_record=kinesis_record,
                dynamodb_client=self.dynamodb_client,
                dynamodb_table=self.table
            )
            base_operation._load_profiles()
            needs_integration = base_operation.needs_integration(
                base_operation.profiles['new_profile'],
                base_operation.profiles['old_profile']
            )
            assert needs_integration is False
            assert base_operation.profiles['new_profile'].verify_all_publishers(
                base_operation.profiles['old_profile']
            ) is True
            assert base_operation.process() is True

        from cis_identity_vault.models import user

        p = user.Profile(self.table)
        p.find_by_id(id=base_operation.profiles['new_profile'].as_dict()['user_id']['value'])

    @patch.object(profile.User, 'verify_all_publishers')
    @patch.object(profile.User, 'verify_all_signatures')
    def test_base_operation_object_it_should_succeed(self, verify_sigs, verify_pubs):
        verify_sigs.return_value = True
        verify_pubs.return_value = True
        os.environ['CIS_PROCESSOR_VERIFY_SIGNATURES'] = 'False'
        patched_profile = self.mr_mozilla_profile
        patched_profile['last_name']['value'] = 'anupdatedlastname'
        kinesis_event = kinesis_event_generate(patched_profile)

        from cis_processor import operation
        for kinesis_record in kinesis_event['Records']:
            base_operation = operation.BaseProcessor(
                event_record=kinesis_record,
                dynamodb_client=self.dynamodb_client,
                dynamodb_table=self.table
            )
            base_operation._load_profiles()
            needs_integration = base_operation.needs_integration(
                base_operation.profiles['new_profile'],
                base_operation.profiles['old_profile']
            )
            assert needs_integration is True
            assert base_operation.profiles['new_profile'].verify_all_publishers(
                base_operation.profiles['old_profile']
            ) is True
            assert base_operation.process() is True

        from cis_identity_vault.models import user

        p = user.Profile(self.table)
        p.find_by_id(id=base_operation.profiles['new_profile'].as_dict()['user_id']['value'])

    @patch.object(profile.User, 'verify_all_publishers')
    @patch.object(profile.User, 'verify_all_signatures')
    def test_base_operation_object_with_signature_testing_it_should_fail(self, verify_sigs, verify_pubs):
        verify_sigs.return_value = False
        verify_pubs.return_value = True
        os.environ['CIS_PROCESSOR_VERIFY_SIGNATURES'] = 'True'
        patched_profile = self.mr_mozilla_profile
        patched_profile['first_name']['value'] = 'anupdatedfirstname'
        kinesis_event = kinesis_event_generate(patched_profile)

        from cis_processor import operation
        for kinesis_record in kinesis_event['Records']:
            base_operation = operation.BaseProcessor(
                event_record=kinesis_record,
                dynamodb_client=self.dynamodb_client,
                dynamodb_table=self.table
            )
            base_operation._load_profiles()
            needs_integration = base_operation.needs_integration(
                base_operation.profiles['new_profile'],
                base_operation.profiles['old_profile']
            )
            assert needs_integration is True
            assert base_operation.profiles['new_profile'].verify_all_publishers(
                base_operation.profiles['old_profile']
            ) is True
            assert base_operation.process() is False

    @patch.object(profile.User, 'verify_all_publishers')
    @patch.object(profile.User, 'verify_all_signatures')
    def test_new_user_scenario(self, verify_sigs, verify_pubs):
        verify_sigs.return_value = False
        verify_pubs.return_value = True
        os.environ['CIS_PROCESSOR_VERIFY_SIGNATURES'] = 'True'
        new_user_profile = fake_profile.FakeUser().as_dict()
        new_user_profile['user_id']['value'] = 'harrypotter'
        kinesis_event = kinesis_event_generate(new_user_profile)

        from cis_processor import operation
        for kinesis_record in kinesis_event['Records']:
            base_operation = operation.BaseProcessor(
                event_record=kinesis_record,
                dynamodb_client=self.dynamodb_client,
                dynamodb_table=self.table
            )
            base_operation._load_profiles()
            needs_integration = base_operation.needs_integration(
                base_operation.profiles['new_profile'],
                base_operation.profiles['old_profile']
            )
            assert needs_integration is True
            assert base_operation.profiles['new_profile'].verify_all_publishers(
                base_operation.profiles['old_profile']
            ) is True
            assert base_operation.process() is False
