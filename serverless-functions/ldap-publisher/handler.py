import boto3
import common
import http.client
import json
import ldap
import logging
import os
import sys


CLIENT_ID_PARAMETER = '/iam/ldap-publisher/{}/client_id'.format(os.getenv('CIS_ENVIRONMENT'))
CLIENT_SECRET_PARAMETER = '/iam/ldap-publisher/{}/client_secret'.format(os.getenv('CIS_ENVIRONMENT'))
AUTHZERO_DOMAIN_PARAMETER = '/iam/ldap-publisher/{}/authzero_domain'.format(os.getenv('CIS_ENVIRONMENT'))


def setup_logging():
    logger = logging.getLogger()
    for h in logger.handlers:
        logger.removeHandler(h)
    h = logging.StreamHandler(sys.stdout)
    FORMAT = '%(message)s'
    h.setFormatter(logging.Formatter(FORMAT))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)
    return logger


def assume_role():
    config = common.get_config()
    role_arn = config('assume_role_arn', namespace='ldap')

    sts = boto3.client('sts')
    credentials = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName='cis-ldap-publisher',
        DurationSeconds=900
    )

    return credentials['Credentials']


def get_parameter(parameter_name):
    ssm = boto3.client('ssm')
    res = ssm.get_parameter(
        Name=parameter_name,
        WithDecryption=True
    )
    return res['Parameter']['Value']


def get_audience():
    config = common.get_config()
    environment = config('environment', namespace='cis')
    if environment == 'development':
        return 'https://api.sso.allizom.org'
    else:
        return 'https://api.sso.mozilla.com'


def exchange_for_access_token(client_id, client_secret, authzero_domain):
    conn = http.client.HTTPSConnection(authzero_domain)
    payload_dict = dict(
        client_id=client_id,
        client_secret=client_secret,
        audience=get_audience(),
        grant_type="client_credentials"
    )

    payload = json.dumps(payload_dict)
    headers = {'content-type': "application/json"}
    conn.request("POST", "/oauth/token", payload, headers)
    res = conn.getresponse()
    data = json.loads(res.read())
    return data['access_token']


def publish_profile(access_token, user_profile):
    config = common.get_config()
    base_url = config('change_endpoint_domain', namespace='cis')
    path = config('change_endpoint_route', namespace='cis')

    conn = http.client.HTTPSConnection(base_url)

    headers = {
        'authorization': "Bearer {}".format(access_token),
        'Content-type': 'application/json'
    }

    conn.request("POST", path, json.dumps(user_profile), headers=headers)
    res = conn.getresponse()
    data = json.loads(res.read())
    return data


def handle(event, context):
    logger = setup_logging()
    credentials = assume_role()
    s3 = boto3.resource(
        's3',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
    )

    ldap_client = ldap.User()
    ldap_client.s3 = s3

    users = ldap_client.all

    authzero_client_id = get_parameter(CLIENT_ID_PARAMETER)
    authzero_client_secret = get_parameter(CLIENT_SECRET_PARAMETER)
    authzero_domain = get_parameter(AUTHZERO_DOMAIN_PARAMETER)
    access_token = exchange_for_access_token(authzero_client_id, authzero_client_secret, authzero_domain)

    success = 0
    failure = 0

    for user in users:
        v2_user_profile = users[user]
        user_id = v2_user_profile['user_id']['value']
        logger.info('Processing integration for user: {}'.format(user_id))
        res = publish_profile(access_token, v2_user_profile)
        logger.info(
            'The result of the attempt to publish the profile was: {} for user: {}'.format(res['status_code'], user_id)
        )

        if res['status_code'] == 200:
            success = success + 1
        else:
            failure = failure + 1

    return {
        'success': success,
        'failure': failure,
        'total_processed': success + failure
    }
