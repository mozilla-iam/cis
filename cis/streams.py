import base64
import boto3
import json

from cis.encryption import encrypt
from cis.settings import KINESIS_STREAM_ARN


kinesis = boto3.client('kinesis')


def publish_to_cis(data, partition_key):
    """
    Publish data to CIS kinesis stream given a partition key.

    :data: Data to be published to kinesis (dict)
    :partition_key: Kinesis partition key used to publish data to
    """

    binary_payload = encrypt(data)

    # Encode to base64 all payload fields
    base64_payload = dict()
    for key in ['ciphertext', 'ciphertext_key', 'iv', 'tag']:
        base64_payload[key] = base64.b64encode(binary_payload[key]).decode('utf-8')

    json_payload = json.dumps(base64_payload).encode('utf-8')

    response = kinesis.put_record(
        StreamName=KINESIS_STREAM_ARN.split('/')[1],
        Data=json_payload,
        PartitionKey=partition_key
    )

    return response
