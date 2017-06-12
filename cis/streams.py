import base64
import boto3
import json

from cis.encryption import encrypt
from cis.settings import get_config


kinesis = boto3.client('kinesis')
lambda_client = boto3.client('lambda')


def prepare_payload(data):
    """
    Encrypt data, base64 encode encrypted fields, prepare binary json

    :data: Data to be published to CIS
    """

    binary_payload = encrypt(data)

    # Encode to base64 all payload fields
    base64_payload = dict()
    for key in ['ciphertext', 'ciphertext_key', 'iv', 'tag']:
        base64_payload[key] = base64.b64encode(binary_payload[key]).decode('utf-8')

    json_payload = json.dumps(base64_payload).encode('utf-8')

    return json_payload


def publish_to_cis(data, partition_key):
    """
    Publish data to CIS kinesis stream given a partition key.

    :data: Data to be published to kinesis (dict)
    :partition_key: Kinesis partition key used to publish data to
    """

    payload = prepare_payload(data)
    config = get_config()
    stream_arn = config('kinesis_stream_arn', namespace='cis')
    stream_name = stream_arn.split('/')[1]
    response = kinesis.put_record(
        StreamName=stream_name,
        Data=payload,
        PartitionKey=partition_key
    )

    return response


def invoke_cis_lambda(data):
    """
    Invoke lambda function in front of the CIS pipeline with data to be pushed to CIS

    :data: Data to be published to CIS (dict)
    """

    payload = prepare_payload(data)
    config = get_config()
    function_name = config('lambda_validator_arn', namespace='cis')
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType='RequestResponse',
        Payload=payload
    )

    return response
