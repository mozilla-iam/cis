import boto3
import json
import os
import subprocess
from botocore.stub import Stubber
from cis_identity_vault import vault


class TestUsersDynalite(object):
    def setup(self):
        self.dynalite_host = 'localhost'
        self.dynalite_port = '4567'
        self.dynaliteprocess = subprocess.Popen(['dynalite', '--port', self.dynalite_port], preexec_fn=os.setsid)
        os.environ['CIS_ENVIRONMENT'] = 'local'
        os.environ['CIS_DYNAMODB_PORT'] = self.dynalite_port
        os.environ['CIS_REGION_NAME'] = 'us-east-1'
        self.vault_client = vault.IdentityVault()
        self.vault_client.connect()
        self.vault_client.find_or_create()
        fh = open('tests/fixture/valid-profile.json')
        self.user_profile = json.loads(fh.read())
        fh.close()

        self.vault_json_datastructure = {
            'id': self.user_profile.get('user_id').get('value'),
            'primary_email': self.user_profile.get('primary_email').get('value'),
            'sequence_number': '12345678',
            'profile': json.dumps(self.user_profile)
        }
        self.boto_session = Stubber(boto3.session.Session(region_name='us-east-1')).client
        self.dynamodb_client = self.boto_session.resource(
            'dynamodb', endpoint_url='http://{}:{}'.format(
                self.dynalite_host,
                self.dynalite_port
            )
        )
        self.table = self.dynamodb_client.Table('local-identity-vault')

    def test_create_method(self):
        from cis_identity_vault.models import user
        profile = user.Profile(self.table)
        result = profile.create(self.vault_json_datastructure)
        assert result is not None

    def test_update_method(self):
        from cis_identity_vault.models import user
        modified_profile = self.user_profile
        modified_profile['primary_email']['value'] = 'dummy@zxy.foo'

        vault_json_datastructure = {
            'id': modified_profile.get('user_id').get('value'),
            'primary_email': modified_profile.get('primary_email').get('value'),
            'sequence_number': '12345678',
            'profile': json.dumps(modified_profile)
        }
        profile = user.Profile(self.table)
        result = profile.update(vault_json_datastructure)
        assert result is not None

    def test_find_user(self):
        from cis_identity_vault.models import user
        modified_profile = self.user_profile
        modified_profile['primary_email']['value'] = 'dummy@zxy.foo'

        vault_json_datastructure = {
            'id': modified_profile.get('user_id').get('value'),
            'primary_email': modified_profile.get('primary_email').get('value'),
            'sequence_number': '12345678',
            'profile': json.dumps(modified_profile)
        }
        profile = user.Profile(self.table)
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
            'primary_email': modified_profile.get('primary_email').get('value'),
            'sequence_number': '12345678',
            'profile': json.dumps(modified_profile)
        }

        profile = user.Profile(self.table)
        result = profile.update(vault_json_datastructure_first_id)

        vault_json_datastructure_second_id = {
            'id': 'foo|mcbar',
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
        assert len(result_for_email.get('Items')) == 2

    def teardown(self):
        os.killpg(os.getpgid(self.dynaliteprocess.pid), 15)
