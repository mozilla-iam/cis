import json
import os
import unittest

from unittest.mock import patch


class PublisherTest(unittest.TestCase):

    def setUp(self):
        fixtures = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data/fixtures.json')

        with open(fixtures) as artifacts:
            self.test_artifacts = json.load(artifacts)
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

    @patch('cis.libs.streams.kinesis')
    @patch('cis.libs.streams.encrypt_payload')
    def test_publish_to_cis_kinesis(self, mock_encrypt, mock_kinesis):
        mock_encrypt.side_effect = [{
            'ciphertext': b'ciphertext',
            'ciphertext_key': b'ciphertext_key',
            'iv': b'iv',
            'tag': b'tag'
        }]
        mock_kinesis.put_record.return_value = {
            'ShardId': 'test-shard-id-string',
            'SequenceNumber': 'test-sequence-number-string'
        }
        test_dict = {'foo': 'bar'}
        test_partition_key = 'foobar'
        test_encrypted_json = {
            'ciphertext': 'Y2lwaGVydGV4dA==',
            'iv': 'aXY=',
            'tag': 'dGFn',
            'ciphertext_key': 'Y2lwaGVydGV4dF9rZXk='
        }

        from cis.libs.streams import publish_to_cis
        response = publish_to_cis(test_dict, test_partition_key)

        self.assertEqual(mock_kinesis.put_record.call_args[1]['StreamName'],
                         self.test_artifacts['dummy_kinesis_arn'].split('/')[1])
        self.assertEqual(mock_kinesis.put_record.call_args[1]['PartitionKey'],
                         test_partition_key)
        self.assertEqual(json.loads(mock_kinesis.put_record.call_args[1]['Data'].decode('utf-8')),
                         test_encrypted_json)
        self.assertEqual(response, mock_kinesis.put_record.return_value)

    @patch('cis.libs.streams.lambda_client')
    @patch('cis.libs.streams.encrypt_payload')
    def test_invoke_validator_lambda(self, mock_encrypt, mock_lambda):
        mock_encrypt.side_effect = [{
            'ciphertext': b'ciphertext',
            'ciphertext_key': b'ciphertext_key',
            'iv': b'iv',
            'tag': b'tag'
        }]
        mock_lambda.invoke.return_value = {
            'StatusCode': 123,
            'ResponseMetadata': {
                'foo': 'bar',
            },
        }

        test_dict = {'foo': 'bar'}
        test_encrypted_json = {
            'ciphertext': 'Y2lwaGVydGV4dA==',
            'iv': 'aXY=',
            'tag': 'dGFn',
            'ciphertext_key': 'Y2lwaGVydGV4dF9rZXk='
        }

        from cis.libs.streams import invoke_cis_lambda
        response = invoke_cis_lambda(test_dict)

        self.assertEqual(mock_lambda.invoke.call_args[1]['FunctionName'],
                         self.test_artifacts['dummy_lambda_validator_arn'])
        self.assertEqual(mock_lambda.invoke.call_args[1]['InvocationType'],
                         'RequestResponse')
        self.assertEqual(json.loads(mock_lambda.invoke.call_args[1]['Payload'].decode('utf-8')),
                         test_encrypted_json)
        self.assertEqual(response, mock_lambda.invoke.return_value)
