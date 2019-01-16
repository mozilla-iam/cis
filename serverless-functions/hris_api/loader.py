import boto3
import json
import requests
from os import getenv
from requests.auth import HTTPBasicAuth


def get_secure_parameter(parameter_name):
    client = boto3.client('ssm')
    response = client.get_parameter(
        Name=parameter_name,
        WithDecryption=True
    )
    return response['Parameter']['Value']


def get_file_from_hris(username, password, url, path):
    params = dict(format='json')
    route = 'https://{}{}'.format(url, path)
    res = requests.get(
        route,
        auth=HTTPBasicAuth(username, password),
        params=params
    )
    return res.json()


def assume_role():
    role_arn = getenv('HRIS_ASSUME_ROLE_ARN', None)
    sts = boto3.client('sts')
    credentials = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName='cis-hris-loader',
        DurationSeconds=900
    )

    return credentials['Credentials']


def store_in_s3(s3_bucket_name, data):
    if getenv('HRIS_ASSUME_ROLE_ARN', None) is None:
        s3 = boto3.resource('s3')
    else:
        credentials = assume_role()
        boto_session = boto3.session.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken'],
        )
        s3 = boto_session.resource('s3')
    bucket = s3.Bucket(s3_bucket_name)
    object = bucket.put_object(
        Body=data,
        Key='workday.json'
    )
    return object


def handle(event=None, context={}):
    cis_environment = getenv('CIS_ENVIRONMENT', 'development')
    hris_url = get_secure_parameter('/iam/hris-publisher/{}/hris_url'.format(cis_environment))
    hris_path = get_secure_parameter('/iam/hris-publisher/{}/hris_path'.format(cis_environment))
    username = get_secure_parameter('/iam/hris-publisher/{}/hris_user'.format(cis_environment))
    password = get_secure_parameter('/iam/hris-publisher/{}/hris_password'.format(cis_environment))
    s3_bucket = get_secure_parameter('/iam/hris-publisher/{}/hris_bucket'.format(cis_environment))

    hris_data = get_file_from_hris(username, password, hris_url, hris_path)
    store_in_s3(s3_bucket, bytes(json.dumps(hris_data).encode('utf-8')))
    return 200
