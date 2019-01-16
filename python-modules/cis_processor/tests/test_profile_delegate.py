import base64
import boto3
import json
import os
import random
from botocore.stub import Stubber
from moto import mock_dynamodb2
from cis_profile import fake_profile

def profile_to_vault_structure(user_profile):
    return {
        'sequence_number': str(random.randint(100000, 100000000)),
        'primary_email': user_profile['primary_email']['value'],
        'profile': json.dumps(user_profile),
        'id': user_profile['user_id']['value']
    }


def kinesis_event_generate(user_profile):
    fh = open('tests/fixture/kinesis-event.json')
    kinesis_event_structure = json.loads(fh.read())
    fh.close()

    kinesis_event_structure['Records'][0]['kinesis']['parititionKey'] = 'generic_publisher'
    kinesis_event_structure['Records'][0]['kinesis']['data'] = base64.b64encode(
        json.dumps(user_profile).encode()
    ).decode()

    return kinesis_event_structure['Records'][0]


@mock_dynamodb2
class TestProfileDelegate(object):
    def setup(self):
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
        self.mr_mozilla_profile = fake_profile.FakeUser(generator=1337).as_dict()

        self.mr_nozilla_tainted_profile = fake_profile.FakeUser(generator=1337).as_dict()


        from cis_identity_vault.models import user
        vault_interface = user.Profile(self.table)
        vault_interface.create(profile_to_vault_structure(user_profile=self.mr_mozilla_profile))
        vault_interface.create(profile_to_vault_structure(user_profile=self.mr_nozilla_tainted_profile))

        self.mr_mozilla_change_event = kinesis_event_generate(self.mr_mozilla_profile)

    def test_vault_is_found(self):
        res = self.vault_client.find()
        assert res is not None

    def test_profile_object_returns_object_it_should_succeed(self):
        from cis_processor.profile import ProfileDelegate
        profile_delegate = ProfileDelegate(self.mr_mozilla_change_event, self.dynamodb_client, self.table)
        old_user_profile = profile_delegate.load_old_user_profile()
        assert old_user_profile.as_json() is not None

        new_user_profile = profile_delegate.load_new_user_profile()
        assert new_user_profile.as_json() is not None

    def test_profile_object_returns_none_for_a_non_existant_user(self):
        from cis_processor.profile import ProfileDelegate

        new_user_id = 'ad|Mozilla-LDAP-Dev|newzilla'
        new_user_stub = {
            'user_id': {
                'value': new_user_id
            },
            'primary_email': {
                'value': 'newzillian@newzilla.com'
            }
        }

        kinesis_event = kinesis_event_generate(user_profile=new_user_stub)

        profile_delegate = ProfileDelegate(kinesis_event, self.dynamodb_client, self.table)
        result = profile_delegate.load_old_user_profile()
        assert result is None
