import boto3
import json
import os
import pytest

from jose import jwk
from moto import mock_ssm


class TestSecretManager(object):
    def test_file_provider(self):
        from cis_crypto import secret
        os.environ['CIS_SECRET_MANAGER_FILE_PATH'] = 'tests/fixture'
        manager = secret.Manager(provider_type='file')
        key_material = manager.get_key('fake-access-file-key.priv.pem')
        assert key_material is not None

    @mock_ssm
    def test_ssm_provider(self):
        from cis_crypto import secret
        os.environ['CIS_SECRET_MANAGER_SSM_PATH'] = '/baz'
        key_dir = 'tests/fixture/'
        key_name = 'fake-access-file-key'
        file_name = '{}.priv.pem'.format(key_name)
        fh = open((os.path.join(key_dir, file_name)), 'rb')
        key_content = fh.read()
        key_construct = jwk.construct(key_content, 'RS256')

        key_dict = key_construct.to_dict()

        for k, v in key_dict.items():
            if isinstance(v, bytes):
                key_dict[k] = v.decode()

        deserialized_key_dict = json.dumps(key_dict)
        client = boto3.client('ssm', region_name='us-west-2')
        client.put_parameter(
            Name='/baz/{}'.format(key_name),
            Description='A secure test parameter',
            Value=deserialized_key_dict,
            Type='SecureString',
            KeyId='alias/aws/ssm'
        )
        manager = secret.Manager(provider_type='aws-ssm')
        key_material = manager.get_key('fake-access-file-key')
        assert key_material is not None

    @mock_ssm
    @pytest.mark.xfail
    def test_ssm_provider_fail(self):
        from cis_crypto import secret
        manager = secret.Manager(provider_type='aws-ssm')
        key_material = manager.get_key('this-key-doesnt-exist')
        assert key_material is not None
