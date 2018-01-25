import base64
import io
import json
import os
import unittest
import zipfile

try:
    from unittest.mock import patch  # Python 3
except Exception as e:
    from mock import patch

from pykmssig import hashes


class PublisherTest(unittest.TestCase):
    def get_test_zip_file(self):
        zip_output = io.BytesIO()
        zip_file = zipfile.ZipFile(zip_output, 'w')
        zip_file.writestr(
            'lambda_function.py', b'''\
            def handler(event, context):
                return True
            '''
        )
        zip_file.close()
        zip_output.seek(0)

        return zip_output.read()

    def setUp(self):
        fixtures = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data/fixtures.json')
        with open(fixtures) as artifacts:
            self.test_artifacts = json.load(artifacts)

        # Load a good and bad profile.
        profile_good_file = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), 'data/profile-good.json')
        profile_bad_file = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), 'data/profile-bad.json')
        profile_vault_file = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), 'data/profile-from-vault.json')

        with open(profile_good_file) as profile_good:
            self.test_profile_good = json.load(profile_good)
        with open(profile_bad_file) as profile_bad:
            self.test_profile_bad = json.load(profile_bad)
        with open(profile_vault_file) as profile_vault:
            self.test_profile_vault = json.load(profile_vault)

        self.good_signatures = base64.b64encode(
            json.dumps(hashes.get_digests(json.dumps(self.test_profile_good))).encode()
        ).decode()

        self.bad_signatures = base64.b64encode(
            json.dumps({'blake2': 'evilsig', 'sha256': 'evilsha'}).encode()
        ).decode()

        os.environ['AWS_DEFAULT_REGION'] = self.test_artifacts['dummy_aws_region']
        # Set environment variables
        """
        * Environment variables used
          * CIS_ARN_MASTER_KEY
          * CIS_DYNAMODB_TABLE
          * CIS_KINESIS_STREAM_ARN
          * CIS_LAMBDA_VALIDATOR_ARN

        """
        os.environ["CIS_ARN_MASTER_KEY"] = self.test_artifacts['dummy_kms_arn']
        os.environ["CIS_DYNAMODB_TABLE"] = self.test_artifacts['dummy_dynamodb_table']
        os.environ["CIS_KINESIS_STREAM_ARN"] = self.test_artifacts['dummy_kinesis_arn']
        os.environ["CIS_LAMBDA_VALIDATOR_ARN"] = self.test_artifacts['dummy_lambda_validator_arn']
        os.environ["CIS_PERSON_API_AUDIENCE"] = self.test_artifacts['dummy_person_api_audience']
        os.environ["CIS_PERSON_API_VERSION"] = self.test_artifacts['dummy_person_api_version']
        os.environ["CIS_PERSON_API_URL"] = self.test_artifacts['dummy_person_api_url']
        os.environ["CIS_OAUTH2_DOMAIN"] = self.test_artifacts['dummy_oauth2_domain']
        os.environ["CIS_OAUTH2_CLIENT_ID"] = self.test_artifacts['dummy_oauth2_client_id']
        os.environ["CIS_OAUTH2_CLIENT_SECRET"] = self.test_artifacts['dummy_oauth2_client_secret']

        self.publisher = str(base64.b64decode(self.test_artifacts['dummy_publisher']))

    def test_object_init(self):
        from cis import publisher

        p = publisher.Change(
            publisher={'id': 'mozilliansorg'},
            signature={},
            profile_data={}
        )

        assert p.publisher is not None

    def test_null_object_init(self):
        from cis import publisher

        p = publisher.Change()

        assert p.publisher is None
        assert p.signature is None
        assert p.profile_data is None

    from cis.publisher import Change

    @patch.object(Change, "_generate_signature")
    @patch.object(Change, "_retrieve_from_vault")
    @patch.object(Change, "_invoke_validator")
    def test_publishing_profile(self, mock_validator, mock_vault_profile, mock_signature, Change=Change):

        from cis.libs import encryption
        o = encryption.Operation(
            boto_session=None
        )

        test_kms_data = {
            'Plaintext': base64.b64decode(self.test_artifacts['Plaintext']),
            'CiphertextBlob': base64.b64decode(self.test_artifacts['CiphertextBlob'])
        }

        test_iv = base64.b64decode(self.test_artifacts['IV'])

        # Set attrs on object to test data.  Not patching boto3 now!
        o.data_key = test_kms_data
        o.iv = test_iv

        mock_vault_profile.return_value = None
        mock_validator.return_value = True
        mock_signature.return_value = self.good_signatures

        p = Change(
            publisher={'id': 'mozilliansorg'},
            signature={},
            profile_data=self.test_profile_good
        )

        p.encryptor = o
        p.boto_session = "I am a real session I swear"
        result = p.send()

        assert result is True

    @patch.object(Change, "_generate_signature")
    @patch.object(Change, "_retrieve_from_vault")
    @patch.object(Change, "_invoke_validator")
    def test_group_reintegration(self, mock_validator, mock_vault_profile, mock_signature, Change=Change):

        from cis.libs import encryption
        o = encryption.Operation(
            boto_session=None
        )

        test_kms_data = {
            'Plaintext': base64.b64decode(self.test_artifacts['Plaintext']),
            'CiphertextBlob': base64.b64decode(self.test_artifacts['CiphertextBlob'])
        }

        test_iv = base64.b64decode(self.test_artifacts['IV'])

        # Set attrs on object to test data.  Not patching boto3 now!
        o.data_key = test_kms_data
        o.iv = test_iv

        mock_vault_profile.return_value = self.test_profile_vault
        mock_validator.return_value = True
        mock_signature.return_value = self.good_signatures

        p = Change(
            publisher={'id': 'mozilliansorg'},
            signature={},
            profile_data=self.test_profile_good
        )

        p.encryptor = o
        p.boto_session = "I am a real session I swear"

        p._prepare_profile_data()

        groups = p.profile_data.get('groups')
        result = p.send()

        assert result is True
        assert 'hris_foo_bar' in groups

    @patch.object(Change, "_generate_signature")
    @patch.object(Change, "_retrieve_from_vault")
    @patch.object(Change, "_invoke_validator")
    def test_group_reintegration_where_no_user(
        self, mock_validator, mock_vault_profile, mock_signature, Change=Change
    ):

        from cis.libs import encryption
        o = encryption.Operation(
            boto_session=None
        )

        test_kms_data = {
            'Plaintext': base64.b64decode(self.test_artifacts['Plaintext']),
            'CiphertextBlob': base64.b64decode(self.test_artifacts['CiphertextBlob'])
        }

        test_iv = base64.b64decode(self.test_artifacts['IV'])

        # Set attrs on object to test data.  Not patching boto3 now!
        o.data_key = test_kms_data
        o.iv = test_iv

        mock_vault_profile.return_value = {}
        mock_validator.return_value = True
        mock_signature.return_value = self.good_signatures

        p = Change(
            publisher={'id': 'mozilliansorg'},
            signature={},
            profile_data=self.test_profile_good
        )

        p.encryptor = o
        p.boto_session = "I am a real session I swear"

        p._prepare_profile_data()

        result = p.send()

        assert result is True
