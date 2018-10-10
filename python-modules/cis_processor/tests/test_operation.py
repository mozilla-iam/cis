import base64
import boto3
import json
import os
import random
import subprocess

from botocore.stub import Stubber
from cis_processor.common import get_config
from cis_identity_vault import vault
from moto import mock_dynamodb2


def profile_to_vault_structure(user_profile):
    return {
        'sequence_number': str(random.randint(100000,100000000)),
        'primary_email': user_profile['primary_email']['value'],
        'profile': json.dumps(user_profile),
        'id': user_profile['user_id']['value']
    }

def kinesis_event_generate(user_profile):
    fh = open('tests/fixture/kinesis-event.json')
    kinesis_event_structure = json.loads(fh.read())
    fh.close()

    kinesis_event_structure['Records'][0]['parititionKey'] = 'generic_publisher'
    kinesis_event_structure['Records'][0]['data'] = base64.b64encode(
        json.dumps(profile_to_vault_structure(user_profile=user_profile)).encode()
    ).decode()

    return kinesis_event_structure


@mock_dynamodb2
class TestOperation(object):
    def setup(self):
        os.environ['CIS_CONFIG_INI'] = 'tests/fixture/mozilla-cis.ini'
        self.config = get_config()
        from cis_fake_well_known import well_known
        self.well_known_json = well_known.MozillaIAM()
        self.well_known_json.randomize_publishers = False
        self.well_known_json.publisher_keys = self.well_known_json._load_publisher_keys()
        os.environ['CIS_CONFIG_INI'] = 'tests/fixture/mozilla-cis.ini'
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

        from cis_identity_vault import vault
        self.vault_client = vault.IdentityVault()
        self.vault_client.boto_session = Stubber(boto3.session.Session(region_name='us-west-2')).client
        self.vault_client.dynamodb_client = self.dynamodb_client
        self.vault_client.find_or_create()
        self.table = self.dynamodb_resource.Table('testing-identity-vault')
        fh = open('tests/fixture/mr-mozilla.json')
        self.mr_mozilla_profile = json.loads(fh.read())
        fh.close()

        fh = open('tests/fixture/mr-nozilla-tainted.json')
        self.mr_nozilla_tainted_profile = json.loads(fh.read())
        fh.close()

        from cis_identity_vault.models import user
        vault_interface = user.Profile(self.table)
        vault_interface.create(profile_to_vault_structure(user_profile=self.mr_mozilla_profile))
        vault_interface.create(profile_to_vault_structure(user_profile=self.mr_nozilla_tainted_profile))
        self.mr_mozilla_change_event = kinesis_event_generate(self.mr_mozilla_profile)

    def test_base_operation_object_it_should_succeed(self):
        well_known_json_data = self.well_known_json.data()
        kinesis_event = kinesis_event_generate(self.mr_mozilla_profile)

        from cis_processor import operation
        for kinesis_record in kinesis_event['Records']:
            base_operation = operation.BaseProcessor(
                event=kinesis_record,
                dynamodb_client=self.dynamodb_client,
                dynamodb_table=self.table
            )
            base_operation._load_profiles()
            needs_integration = base_operation.needs_integration(
                base_operation.profiles['new_profile'],
                base_operation.profiles['old_profile']
            )
            assert needs_integration is False
            assert base_operation.profiles['new_profile'].verify_all_publishers() is True
            base_operation.process()
            assert 0
