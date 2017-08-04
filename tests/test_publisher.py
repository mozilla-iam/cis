import base64
import io
import json
import os
import unittest
import zipfile

from unittest.mock import patch


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

        with open(profile_good_file) as profile_good:
            self.test_profile_good = json.load(profile_good)
        with open(profile_bad_file) as profile_bad:
            self.test_profile_bad = json.load(profile_bad)

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

        self.publisher = str(base64.b64decode(self.test_artifacts['dummy_publisher']))

    def test_object_init(self):
        from cis import publisher

        p = publisher.Change(
            publisher={'id': 'mozillians.org'},
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

    @patch.object(Change, "_invoke_validator")
    def test_publishing_profile(self, mock_validator, Change=Change):

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

        mock_validator.return_value = True

        p = Change(
            publisher={'id': 'mozillians.org'},
            signature={},
            profile_data=self.test_profile_good
        )

        p.encryptor = o

        p.boto_session = "I am a real session I swear"

        result = p.send()

        print(result)

        assert result is True
