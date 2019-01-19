import boto3
import json
import os
import uuid
from cis_identity_vault import vault
from cis_profile import FakeUser
from moto import mock_dynamodb2


@mock_dynamodb2
class TestUsersDynalite(object):
    def setup(self):
        os.environ['CIS_ENVIRONMENT'] = 'testing'
        os.environ['CIS_REGION_NAME'] = 'us-east-1'
        self.vault_client = vault.IdentityVault()
        self.vault_client.connect()
        self.vault_client.find_or_create()

        self.user_profile = FakeUser().as_dict()
        self.uuid = self.user_profile['uuid']['value']
        self.vault_json_datastructure = {
            'id': self.user_profile.get('user_id').get('value'),
            'uuid': self.uuid,
            'primary_email': self.user_profile.get('primary_email').get('value'),
            'sequence_number': '12345678',
            'profile': json.dumps(self.user_profile)
        }
        self.boto_session = boto3.session.Session(region_name='us-east-1')
        self.dynamodb_resource = self.boto_session.resource(
            'dynamodb'
        )
        self.dynamodb_client = self.boto_session.client('dynamodb')
        self.table = self.dynamodb_resource.Table('testing-identity-vault')

    def test_create_method(self):
        from cis_identity_vault.models import user
        profile = user.Profile(
            self.table,
            self.dynamodb_client,
            transactions=False
        )
        result = profile.create(self.vault_json_datastructure)
        assert result is not None

    def test_update_method(self):
        from cis_identity_vault.models import user
        modified_profile = self.user_profile
        modified_profile['primary_email']['value'] = 'dummy@zxy.foo'

        vault_json_datastructure = {
            'id': modified_profile.get('user_id').get('value'),
            'uuid': str(uuid.uuid4()),
            'primary_email': modified_profile.get('primary_email').get('value'),
            'sequence_number': '12345678',
            'profile': json.dumps(modified_profile)
        }
        profile = user.Profile(
            self.table,
            self.dynamodb_client,
            transactions=False
        )
        result = profile.update(vault_json_datastructure)
        assert result is not None

    def test_find_user(self):
        from cis_identity_vault.models import user
        modified_profile = self.user_profile
        modified_profile['primary_email']['value'] = 'dummy@zxy.foo'

        vault_json_datastructure = {
            'id': modified_profile.get('user_id').get('value'),
            'uuid': str(uuid.uuid4()),
            'primary_email': modified_profile.get('primary_email').get('value'),
            'sequence_number': '12345678',
            'profile': json.dumps(modified_profile)
        }
        profile = user.Profile(
            self.table,
            self.dynamodb_client,
            transactions=False
        )

        profile.update(vault_json_datastructure)

        primary_email = 'dummy@zxy.foo'
        profile = user.Profile(self.table)
        user_id = self.user_profile.get('user_id').get('value')
        result_for_user_id = profile.find_by_id(user_id)
        result_for_email = profile.find_by_email(primary_email)
        assert result_for_user_id is not None
        assert result_for_email is not None

    def test_find_user_multi_id_for_email(self):
        from cis_identity_vault.models import user
        modified_profile = self.user_profile
        modified_profile['primary_email']['value'] = 'dummy@zxy.foo'

        vault_json_datastructure_first_id = {
            'id': modified_profile.get('user_id').get('value'),
            'uuid': str(uuid.uuid4()),
            'primary_email': modified_profile.get('primary_email').get('value'),
            'sequence_number': '12345678',
            'profile': json.dumps(modified_profile)
        }

        profile = user.Profile(
            self.table,
            self.dynamodb_client,
            transactions=False
        )

        profile.update(vault_json_datastructure_first_id)

        vault_json_datastructure_second_id = {
            'id': 'foo|mcbar',
            'uuid': str(uuid.uuid4()),
            'primary_email': modified_profile.get('primary_email').get('value'),
            'sequence_number': '12345678',
            'profile': json.dumps(modified_profile)
        }

        profile.update(vault_json_datastructure_second_id)

        primary_email = 'dummy@zxy.foo'
        profile = user.Profile(self.table)
        self.user_profile.get('user_id').get('value')
        result_for_email = profile.find_by_email(primary_email)
        assert result_for_email is not None
        assert len(result_for_email.get('Items')) > 2

    def test_find_by_uuid(self):
        from cis_identity_vault.models import user

        profile = user.Profile(
            self.table,
            self.dynamodb_client,
            transactions=False
        )

        user = json.loads(profile.all[0].get('profile'))

        result_for_uuid = profile.find_by_uuid(user['uuid']['value'])
        assert len(result_for_uuid.get('Items')) > 0
