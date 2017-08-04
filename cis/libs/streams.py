import base64
import json

from cis.settings import get_config


class Operation(object):
    def __init__(self, boto_session, publisher, signature, encrypted_profile_data):
        self.boto_session = boto_session
        self.config = get_config()
        self.encrypted_profile_data = encrypted_profile_data
        self.publisher = publisher
        self.signature = signature
        self.kinesis_client = None

    def to_kinesis(self):
        """
        Publish data to CIS kinesis stream given a partition key.

        :data: Data to be published to kinesis (dict)
        :partition_key: Kinesis partition key used to publish data to
        """

        if not self.kinesis_client:
            self.kinesis_client = self.boto_session.client('kinesis')

        event = {
            'publisher': self.publisher,
            'profile': self.encrypted_profile_data,
            'signature': self.signature
        }

        stream_name = self.config('kinesis_stream_name', namespace='cis')

        response = self.kinesis_client.put_record(
            StreamName=stream_name,
            Data=self._encode_encrypted_profile(event),
            PartitionKey=self.publisher.get('id', None)
        )

        return response

    def _encode_encrypted_profile(self, event):
        binary_payload = event['profile']

        base64_payload = dict()
        for key in ['ciphertext', 'ciphertext_key', 'iv', 'tag']:
            base64_payload[key] = base64.b64encode(binary_payload[key]).decode('utf-8')

        base64_payload['signature'] = event.get('signature')

        json_payload = json.dumps(base64_payload).encode('utf-8')
        return json_payload
