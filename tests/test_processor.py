import base64
import boto3
import json
import os
import unittest

from unittest.mock import patch

from moto import mock_kinesis


class ProcessorTest(unittest.TestCase):
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
        os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "foo_bar_bat_validator"


        self.publisher = str(base64.b64decode(self.test_artifacts['dummy_publisher']))

    def test_object_init(self):
        from cis import processor
        p = processor.Operation()


    def test_processor_decrypt(self):
        from cis.libs import encryption

        o = encryption.Operation(
            boto_session = None
        )

        test_kms_data = {
            'Plaintext': base64.b64decode(self.test_artifacts['Plaintext']),
            'CiphertextBlob': base64.b64decode(self.test_artifacts['CiphertextBlob'])
        }

        test_iv = base64.b64decode(self.test_artifacts['IV'])

        # Set attrs on object to test data.  Not patching boto3 now!
        o.data_key = test_kms_data
        o.iv = test_iv
        o.plaintext_key = base64.b64decode(self.test_artifacts['Plaintext'])

        encrypted_profile = o.encrypt(json.dumps(self.test_profile_good).encode())

        publisher = 'mozillians.org'

        from cis import processor

        p = processor.Operation(
            boto_session=None,
            publisher=publisher,
            signature={},
            encrypted_profile_data=encrypted_profile
        )

        p.user = self.test_profile_good


        p.decryptor = o

        p.run()

        assert json.dumps(p.decrytped_profile) == json.dumps(self.test_profile_good)

    def test_processor_validator(self):
        from cis.libs import encryption

        o = encryption.Operation(
            boto_session = None
        )

        test_kms_data = {
            'Plaintext': base64.b64decode(self.test_artifacts['Plaintext']),
            'CiphertextBlob': base64.b64decode(self.test_artifacts['CiphertextBlob'])
        }

        test_iv = base64.b64decode(self.test_artifacts['IV'])

        # Set attrs on object to test data.  Not patching boto3 now!
        o.data_key = test_kms_data
        o.iv = test_iv
        o.plaintext_key = base64.b64decode(self.test_artifacts['Plaintext'])

        encrypted_profile = o.encrypt(json.dumps(self.test_profile_good).encode())

        publisher = 'mozillians.org'

        from cis import processor

        p = processor.Operation(
            boto_session=None,
            publisher=publisher,
            signature={},
            encrypted_profile_data=encrypted_profile
        )

        # Fake like the user returned from dynamo by returning same profile.
        p.user = self.test_profile_good

        # Decrypt with fake key material.
        p.decryptor = o

        res = p.run()

        assert res == True

    @mock_kinesis
    def test_processor_kinesis(self):
        from cis.libs import encryption



        o = encryption.Operation(
            boto_session = None
        )

        test_kms_data = {
            'Plaintext': base64.b64decode(self.test_artifacts['Plaintext']),
            'CiphertextBlob': base64.b64decode(self.test_artifacts['CiphertextBlob'])
        }

        test_iv = base64.b64decode(self.test_artifacts['IV'])

        # Set attrs on object to test data.  Not patching boto3 now!
        o.data_key = test_kms_data
        o.iv = test_iv
        o.plaintext_key = base64.b64decode(self.test_artifacts['Plaintext'])

        encrypted_profile = o.encrypt(json.dumps(self.test_profile_good).encode())

        publisher = 'mozillians.org'

        from cis import processor

        p = processor.Operation(
            boto_session=None,
            publisher=publisher,
            signature={},
            encrypted_profile_data=encrypted_profile
        )

        # Fake like the user returned from dynamo by returning same profile.
        p.user = self.test_profile_good

        p.dry_run = False

        p.kinesis_client = boto3.client('kinesis')

        # Decrypt with fake key material.
        p.decryptor = o

        res = p.run()

        assert res == True