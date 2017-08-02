import base64
import json
import os
import unittest

from unittest.mock import patch


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

    @patch('cis.libs.encryption.kms')
    @patch('cis.libs.encryption.os')
    def test_encrypt_payload(self, mock_os, mock_kms):
        test_kms_data = {
            'Plaintext': base64.b64decode(self.test_artifacts['Plaintext']),
            'CiphertextBlob': base64.b64decode(self.test_artifacts['CiphertextBlob'])
        }
        test_iv = base64.b64decode(self.test_artifacts['IV'])

        mock_kms.generate_data_key.return_value = test_kms_data
        mock_os.urandom.return_value = test_iv

        expected_result = {
            'ciphertext': base64.b64decode(self.test_artifacts['expected_ciphertext']),
            'ciphertext_key': test_kms_data['CiphertextBlob'],
            'iv': test_iv,
            'tag': base64.b64decode(self.test_artifacts['expected_tag'])
        }

        from cis.libs.encryption import encrypt_payload
        self.assertEqual(expected_result, encrypt_payload(b'foobar'))
        mock_kms.generate_data_key.assert_called_once_with(
            KeyId=self.test_artifacts['dummy_kms_arn'],
            KeySpec='AES_256',
            EncryptionContext={}
        )

    @patch('cis.libs.encryption.kms')
    def test_decrypt_payload(self, mock_kms):
        test_kms_data = {
            'Plaintext': base64.b64decode(self.test_artifacts['Plaintext']),
            'CiphertextBlob': base64.b64decode(self.test_artifacts['CiphertextBlob'])
        }
        mock_kms.decrypt.return_value = test_kms_data

        test_iv = base64.b64decode(self.test_artifacts['IV'])

        kwargs = {
            'ciphertext': base64.b64decode(self.test_artifacts['expected_ciphertext']),
            'ciphertext_key': test_kms_data['CiphertextBlob'],
            'iv': test_iv,
            'tag': base64.b64decode(self.test_artifacts['expected_tag'])
        }

        from cis.libs.encryption import decrypt_payload
        self.assertEqual(decrypt_payload(**kwargs), b'foobar')
        mock_kms.decrypt.assert_called_once_with(
            CiphertextBlob=test_kms_data['CiphertextBlob'],
            EncryptionContext={}
        )
