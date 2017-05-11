import base64
import json
import os
import unittest

from unittest.mock import patch


class ValidationTest(unittest.TestCase):
    def setUp(self):
        # Load json with test data
        fixtures = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data/fixtures.json')
        with open(fixtures) as artifacts:
            self.test_artifacts = json.load(artifacts)

        # Setup env vars with dummy AWS credentials
        os.environ['CIS_ARN_MASTER_KEY'] = self.test_artifacts['dummy_kms_arn']
        os.environ['AWS_DEFAULT_REGION'] = self.test_artifacts['dummy_aws_region']

        # Test json schema to validate test payload
        self.test_json_schema = {
            'title': 'Test CIS schema',
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'foo': {
                    'type': 'string'
                }
            }
        }

        # Precomputed test KMS derived keys
        self.test_kms_data = {
            'Plaintext': base64.b64decode(self.test_artifacts['Plaintext']),
            'CiphertextBlob': base64.b64decode(self.test_artifacts['CiphertextBlob'])
        }

        # Precomputed AES IV vector
        self.test_iv = base64.b64decode(self.test_artifacts['IV'])

        self.payload = {
            'ciphertext': base64.b64decode(self.test_artifacts['expected_ciphertext']),
            'ciphertext_key': self.test_kms_data['CiphertextBlob'],
            'iv': self.test_iv,
            'tag': base64.b64decode(self.test_artifacts['expected_tag'])
        }

    @patch('cis.encryption.kms')
    def test_valid_payload_schema(self, mock_kms):
        mock_kms.generate_data_key.return_value = self.test_kms_data
        mock_kms.decrypt.return_value = self.test_kms_data

        from cis.encryption import encrypt

        # Generate valid encrypted payload
        payload = encrypt(b'{"foo": "bar"}')

        with patch('cis.validation.CIS_SCHEMA', self.test_json_schema):
            from cis.validation import validate
            self.assertTrue(validate(**payload))

    @patch('cis.encryption.kms')
    def test_invalid_payload_schema(self, mock_kms):
        mock_kms.generate_data_key.return_value = self.test_kms_data
        mock_kms.decrypt.return_value = self.test_kms_data

        from cis.encryption import encrypt

        # Generate invalid encrypted payload
        payload = encrypt(b'{"foo": 42}')

        with patch('cis.validation.CIS_SCHEMA', self.test_json_schema):
            from cis.validation import validate
            self.assertFalse(validate(**payload))

    @patch('cis.encryption.kms')
    def test_invalid_kms_key(self, mock_kms):
        mock_kms.generate_data_key.return_value = self.test_kms_data
        mock_kms.decrypt.side_effect = Exception('KMS exception')

        from cis.encryption import encrypt

        # Generate invalid encrypted payload
        payload = encrypt(b'{"foo": "bar"}')

        with patch('cis.validation.CIS_SCHEMA', self.test_json_schema):
            from cis.validation import validate
            is_valid_payload = validate(**payload)
        self.assertFalse(is_valid_payload)
