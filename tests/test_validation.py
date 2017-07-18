import base64
import json
import os
import unittest

from unittest.mock import Mock, patch


class ValidationTest(unittest.TestCase):
    def setUp(self):
        # Load json with test data
        fixtures = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data/fixtures.json')
        profile_good_file = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data/fixtures.json')
        profile_bad_file = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data/fixtures.json')

        with open(fixtures) as artifacts:
            self.test_artifacts = json.load(artifacts)
        with open(profile_good_file) as profile_good:
            self.test_profile_good = json.load(profile_good)
        with open(profile_bad_file) as profile_bad:
            self.test_profile_bad = json.load(profile_bad)

        # Precomputed test KMS derived keys
        self.test_kms_data = {
            'Plaintext': base64.b64decode(self.test_artifacts['Plaintext']),
            'CiphertextBlob': base64.b64decode(self.test_artifacts['CiphertextBlob'])
        }

        # Precomputed AES IV
        self.test_iv = base64.b64decode(self.test_artifacts['IV'])

        self.payload = {
            'ciphertext': base64.b64decode(self.test_artifacts['expected_ciphertext']),
            'ciphertext_key': self.test_kms_data['CiphertextBlob'],
            'iv': self.test_iv,
            'tag': base64.b64decode(self.test_artifacts['expected_tag'])
        }

        self.publisher = str(base64.b64decode(self.test_artifacts['dummy_publisher']))

    @patch('cis.encryption.kms')
    def test_valid_payload_schema(self, mock_kms):
        mock_kms.generate_data_key.return_value = self.test_kms_data

        import cis.encryption
        payload = cis.encryption.encrypt(json.dumps(self.test_profile_good).encode())
        publisher = "foo"

        from cis.validation import validate
        self.assertTrue(validate(publisher, **payload))

    @patch('cis.encryption.kms')
    def test_invalid_payload_schema(self, mock_kms):
        mock_kms.generate_data_key.return_value = self.test_kms_data
        mock_kms.decrypt.return_value = self.test_kms_data

        import cis.encryption
        payload = cis.encryption.encrypt(json.dumps(self.test_profile_bad).encode())
        publisher = "foo"

        from cis.validation import validate
        self.assertFalse(validate(publisher, **payload))

    @patch('cis.encryption.kms')
    def test_missing_publisher_schema(self, mock_kms):
        mock_kms.generate_data_key.return_value = self.test_kms_data
        mock_kms.decrypt.return_value = self.test_kms_data

        import cis.encryption
        payload = cis.encryption.encrypt(json.dumps(self.test_profile_good).encode())
        publisher = None

        from cis.validation import validate
        self.assertFalse(validate(publisher, **payload))

    @patch('cis.encryption.kms')
    def test_invalid_kms_key(self, mock_kms):
        return True
        mock_kms.generate_data_key.return_value = self.test_kms_data
        mock_kms.decrypt.side_effect = Exception('KMS exception')

        from cis.encryption import encrypt

        payload = encrypt(json.dumps(self.test_profile_bad).encode())
        publisher = "foo"

        from cis.validation import validate
        is_valid_payload = validate(publisher, **payload)
        self.assertFalse(is_valid_payload)


class DatabaseTest(unittest.TestCase):
    def setUp(self):
        # Load json with test data
        fixtures = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data/fixtures.json')
        with open(fixtures) as artifacts:
            self.test_artifacts = json.load(artifacts)

        # Setup env vars with dummy AWS credentials
        os.environ['CIS_DYNAMODB_TABLE'] = self.test_artifacts['dummy_dynamodb_table']

    @patch('cis.validation.table')
    @patch('cis.validation.dynamodb')
    def test_retrieve_success(self, mock_dynamodb, mock_table):
        mock_table.get_item.return_value = {
            'ResponseMetadata': {
                'HTTPStatusCode': 200,
            }
        }
        from cis.validation import retrieve_from_vault
        user = 'cis|testuser'
        user_key = {
                'user_id': user
        }
        response = retrieve_from_vault(user)
        self.assertEqual(response, mock_table.get_item.return_value)

    @patch('cis.validation.table')
    @patch('cis.validation.dynamodb')
    def test_retrieve_failure(self, mock_dynamodb, mock_table):
        mock_table.get_item.side_effect = Exception('DynamoDB exception')
        from cis.validation import retrieve_from_vault
        user = 'cis|testuser'
        user_key = {
                'user_id': user
        }
        response = retrieve_from_vault(user)
        self.assertEqual(response, None)

    @patch('cis.validation.table')
    @patch('cis.validation.dynamodb')
    def test_store_success(self, mock_dynamodb, mock_table):
        mock_table.put_item.return_value = {
            'ResponseMetadata': {
                'HTTPStatusCode': 200,
            }
        }

        data = {
            'foo': 'bar',
            'foobar': 42
        }

        from cis.validation import store_to_vault
        response = store_to_vault(data)
        self.assertEqual(response, mock_table.put_item.return_value)

    @patch('cis.validation.table')
    @patch('cis.validation.dynamodb')
    def test_store_failure(self, mock_dynamodb, mock_table):
        mock_table.put_item.side_effect = Exception('DynamoDB exception')

        data = {
            'foo': 'bar',
            'foobar': 42
        }

        from cis.validation import store_to_vault
        response = store_to_vault(data)
        self.assertEqual(response, None)
