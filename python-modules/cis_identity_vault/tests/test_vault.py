import os
import subprocess
from moto import mock_dynamodb2


class TestVault(object):
    @mock_dynamodb2
    def test_crud_it_should_succeed(self):
        from cis_identity_vault import vault
        v = vault.IdentityVault()
        os.environ['CIS_ENVIRONMENT'] = 'purple'
        v.connect()
        result = v.create()
        assert result['ResponseMetadata']['HTTPStatusCode'] == 200
        result = v.find()
        assert result == 'arn:aws:dynamodb:us-east-1:123456789011:table/purple-identity-vault'
        result = v.tag_vault()
        assert result['ResponseMetadata']['HTTPStatusCode'] == 200
        result = v.find_or_create()
        assert result is not None
        result = v.destroy()
        assert result['ResponseMetadata']['HTTPStatusCode'] == 200

    @mock_dynamodb2
    def test_find_or_create_will_create(self):
        from cis_identity_vault import vault
        v = vault.IdentityVault()
        v.connect()
        result = v.find_or_create()
        assert result is not None


class TestVaultDynalite(object):
    def setup(self):
        dynalite_port = '9567'
        self.dynaliteprocess = subprocess.Popen(['dynalite', '--port', dynalite_port], preexec_fn=os.setsid)

    def test_create_using_dynalite(self):
        os.environ['CIS_ENVIRONMENT'] = 'local'
        os.environ['CIS_DYNALITE_PORT'] = '9567'
        os.environ['CIS_REGION_NAME'] = 'us-east-1'
        from cis_identity_vault import vault
        v = vault.IdentityVault()
        v.connect()
        result = v.find_or_create()
        assert result is not None

    def teardown(self):
        os.killpg(os.getpgid(self.dynaliteprocess.pid), 15)
