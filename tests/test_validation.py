import base64
import json
import os
import unittest

from unittest.mock import Mock, patch


class ValidationTest(unittest.TestCase):
    def setUp(self):
        # Load json with test data
        fixtures = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data/fixtures.json')
        with open(fixtures) as artifacts:
            self.test_artifacts = json.load(artifacts)

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

    def test_valid_json_payload_schema(self):

        # Generate valid json string
        json_str = '{"foo": "bar"}'

        with patch('cis.validation.CIS_SCHEMA', self.test_json_schema):
            from cis.validation import validate_json
            self.assertTrue(validate_json(json_str))

    def test_invalid_json_payload_schema(self):

        # Generate invalid json string
        json_str = '{"foo": 42}'

        with patch('cis.validation.CIS_SCHEMA', self.test_json_schema):
            from cis.validation import validate_json
            self.assertFalse(validate_json(json_str))


class DatabaseTest(unittest.TestCase):
    def setUp(self):
        # Load json with test data
        fixtures = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data/fixtures.json')
        with open(fixtures) as artifacts:
            self.test_artifacts = json.load(artifacts)

        # Setup env vars with dummy AWS credentials
        os.environ['CIS_DYNAMODB_TABLE'] = self.test_artifacts['dummy_dynamodb_table']

    @patch('cis.validation.boto3')
    def test_store_success(self, mock_boto):
        dynamodb_mock = Mock()
        dynamodb_table = Mock()
        dynamodb_table.put_item.return_value = {
            'ResponseMetadata': {
                'HTTPStatusCode': 200,
            }
        }

        dynamodb_mock.Table.return_value = dynamodb_table
        mock_boto.resource.return_value = dynamodb_mock

        data = {
            'foo': 'bar',
            'foobar': 42
        }

        from cis.validation import store_to_vault
        response = store_to_vault(data)

        mock_boto.resource.assert_called_with('dynamodb')
        dynamodb_mock.Table.assert_called_with('test_dynamodb_table')
        dynamodb_table.put_item.assert_called_with(Item=data)
        self.assertEqual(response, dynamodb_table.put_item.return_value)

    @patch('cis.validation.boto3')
    def test_store_failure(self, mock_boto):
        dynamodb_mock = Mock()
        dynamodb_table = Mock()
        dynamodb_table.put_item.side_effect = Exception('DynamoDB exception')
        dynamodb_mock.Table.return_value = dynamodb_table
        mock_boto.resource.return_value = dynamodb_mock

        data = {
            'foo': 'bar',
            'foobar': 42
        }

        from cis.validation import store_to_vault
        response = store_to_vault(data)

        mock_boto.resource.assert_called_with('dynamodb')
        dynamodb_mock.Table.assert_called_with('test_dynamodb_table')
        dynamodb_table.put_item.assert_called_with(Item=data)
        self.assertEqual(response, None)
