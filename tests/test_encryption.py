import base64
import json
import os
import unittest


class EncryptionTest(unittest.TestCase):

    def setUp(self):
        fixtures = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data/fixtures.json')
        with open(fixtures) as artifacts:
            self.test_artifacts = json.load(artifacts)

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

    def test_object_init(self):

        from cis.libs import encryption

        o = encryption.Operation(
            boto_session = None
        )

        assert o is not None

    def test_encryption(self):

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

        operation_result = o.encrypt(b'foobar')

        expected_result = {
            'ciphertext': base64.b64decode(self.test_artifacts['expected_ciphertext']),
            'ciphertext_key': test_kms_data['CiphertextBlob'],
            'iv': test_iv,
            'tag': base64.b64decode(self.test_artifacts['expected_tag'])
        }

        self.assertEqual(operation_result, expected_result)

    def test_decryption(self):

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
        o.plaintext_key = test_kms_data['Plaintext']

        kwargs = {
            'ciphertext': base64.b64decode(self.test_artifacts['expected_ciphertext']),
            'ciphertext_key': test_kms_data['CiphertextBlob'],
            'iv': test_iv,
            'tag': base64.b64decode(self.test_artifacts['expected_tag'])
        }

        operation_result = o.decrypt(**kwargs)

        expected_result = {
            'ciphertext': base64.b64decode(self.test_artifacts['expected_ciphertext']),
            'ciphertext_key': test_kms_data['CiphertextBlob'],
            'iv': test_iv,
            'tag': base64.b64decode(self.test_artifacts['expected_tag'])
        }

        self.assertEqual(operation_result, b'foobar')