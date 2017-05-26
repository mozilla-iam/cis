import json
import os
import unittest

from unittest.mock import patch


class KinesisPublisherTest(unittest.TestCase):

    def setUp(self):
        fixtures = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data/fixtures.json')

        with open(fixtures) as artifacts:
            self.test_artifacts = json.load(artifacts)
        os.environ['CIS_KINESIS_STREAM_ARN'] = self.test_artifacts['dummy_kinesis_arn']

    @patch('cis.streams.kinesis')
    @patch('cis.streams.encrypt')
    def test_publish_to_cis(self, mock_encrypt, mock_kinesis):
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

        from cis.streams import publish_to_cis
        response = publish_to_cis(test_dict, test_partition_key)

        self.assertEqual(mock_kinesis.put_record.call_args[1]['StreamARN'],
                         self.test_artifacts['dummy_kinesis_arn'])
        self.assertEqual(mock_kinesis.put_record.call_args[1]['PartitionKey'],
                         test_partition_key)
        self.assertEqual(json.loads(mock_kinesis.put_record.call_args[1]['Data'].decode('utf-8')),
                         test_encrypted_json)
        self.assertEqual(response, mock_kinesis.put_record.return_value)
