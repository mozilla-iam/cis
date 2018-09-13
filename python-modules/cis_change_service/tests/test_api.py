import boto3
import json
import logging
import mock
import os
import subprocess
from botocore.stub import Stubber
from boto.kinesis.exceptions import ResourceInUseException
from cis_change_service import api
from datetime import datetime
from datetime import timedelta
from tests.fake_auth0 import FakeBearer
from tests.fake_auth0 import json_form_of_pk


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s:%(levelname)s:%(name)s:%(message)s'
)

logging.getLogger('boto').setLevel(logging.CRITICAL)
logging.getLogger('boto3').setLevel(logging.CRITICAL)
logging.getLogger('botocore').setLevel(logging.CRITICAL)


logger = logging.getLogger(__name__)


class TestAPI(object):
    def setup_class(self):
        api.app.testing = True
        self.app = api.app.test_client()
        os.environ['CIS_CONFIG_INI'] = 'tests/mozilla-cis.ini'
        from cis_change_service import get_config
        config = get_config()
        kinesalite_port = config('kinesalite_port', namespace='cis')
        kinesalite_host = config('kinesalite_host', namespace='cis')
        dynalite_port = config('dynalite_port', namespace='cis')
        subprocess.Popen(['kinesalite', '--port', kinesalite_port])
        subprocess.Popen(['dynalite', '--port', dynalite_port])

        conn = Stubber(
            boto3.session.Session(
                region_name='us-west-2'
            )
        ).client.client(
            'kinesis',
            endpoint_url='http://localhost:{}'.format(kinesalite_port).format(
                kinesalite_host,
                kinesalite_port
            )
        )

        try:
            name = 'local-stream'
            conn.create_stream(
                StreamName=name,
                ShardCount=1
            )
        except ResourceInUseException:
            # This just means we tried too many tests too fast.
            pass

        waiter = conn.get_waiter('stream_exists')

        waiter.wait(
            StreamName=name,
            Limit=100,
            WaiterConfig={
                'Delay': 30,
                'MaxAttempts': 5
            }
        )

        tags_1 = {'Key': 'cis_environment', 'Value': 'local'}
        tags_2 = {'Key': 'application', 'Value': 'change-stream'}
        conn.add_tags_to_stream(StreamName=name, Tags=tags_1)
        conn.add_tags_to_stream(StreamName=name, Tags=tags_2)

        name = 'local-identity-vault'
        conn = boto3.client('dynamodb',
                            region_name='us-west-2',
                            aws_access_key_id="ak",
                            aws_secret_access_key="sk",
                            endpoint_url='http://localhost:{}'.format(dynalite_port))

        conn.create_table(
            TableName=name,
            KeySchema=[
                {'AttributeName': 'id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'id', 'AttributeType': 'S'},  # auth0 user_id
                {'AttributeName': 'sequence_number', 'AttributeType': 'S'},  # sequence number for the last integration
                {'AttributeName': 'primaryEmail', 'AttributeType': 'S'},  # value of the primaryEmail attribute
                {'AttributeName': 'profile', 'AttributeType': 'S'}  # profile json for the v2 profile as a dumped string
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5
            },
            GlobalSecondaryIndexes=[
                {
                    'IndexName': '{}-sequence_number'.format(name),
                    'KeySchema': [
                        {
                            'AttributeName': 'sequence_number',
                            'KeyType': 'HASH'
                        },
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL',
                    },
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                },
                {
                    'IndexName': '{}-primaryEmail'.format(name),
                    'KeySchema': [
                        {
                            'AttributeName': 'primaryEmail',
                            'KeyType': 'HASH'
                        },
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL',
                    },
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                }
            ]
        )

    def test_index_exists(self):
        result = self.app.get('/', follow_redirects=True)
        assert result.status_code == 200

    @mock.patch('cis_change_service.idp.get_jwks')
    def test_change_endpoint_returns(self, fake_jwks):
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk
        token = f.generate_bearer_without_scope()
        api.app.testing = True
        self.app = api.app.test_client()
        fh = open('tests/fixture/valid-profile.json')
        user_profile = json.loads(fh.read())
        fh.close()
        user_profile = user_profile
        result = self.app.post(
            '/change',
            headers={
                'Authorization': 'Bearer ' + token
            },
            data=json.dumps(user_profile),
            content_type='application/json',
            follow_redirects=True
        )

        response = json.loads(result.get_data())
        assert response.get('sequence_number') is not None
        assert response.get('status_code') == 200
        assert result.status_code == 200

    @mock.patch('cis_change_service.idp.get_jwks')
    def test_change_endpoint_fails_with_invalid_token(self, fake_jwks):
        f = FakeBearer()
        bad_claims = {
            'iss': 'https://auth-dev.mozilla.auth0.com/',
            'sub': 'mc1l0G4sJI2eQfdWxqgVNcRAD9EAgHib@clients',
            'aud': 'https://hacks',
            'iat': (datetime.utcnow() - timedelta(seconds=3100)).strftime('%s'),
            'exp': (datetime.utcnow() - timedelta(seconds=3100)).strftime('%s'),
            'scope': 'read:allthething',
            'gty': 'client-credentials'
        }

        fake_jwks.return_value = json_form_of_pk
        token = f.generate_bearer_with_scope('read:profile', bad_claims)
        api.app.testing = True
        self.app = api.app.test_client()
        result = self.app.get(
            '/change',
            headers={
                'Authorization': 'Bearer ' + token
            },
            follow_redirects=True
        )

        assert result.status_code == 401

    @mock.patch('cis_change_service.idp.get_jwks')
    def test_stream_bypass_publishing_mode_it_should_succeed(self, fake_jwks):
        os.environ['CIS_STREAM_BYPASS'] = 'true'
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk
        token = f.generate_bearer_without_scope()
        api.app.testing = True
        self.app = api.app.test_client()
        fh = open('tests/fixture/valid-profile.json')
        user_profile = json.loads(fh.read())
        fh.close()
        user_profile = user_profile
        result = self.app.post(
            '/change',
            headers={
                'Authorization': 'Bearer ' + token
            },
            data=json.dumps(user_profile),
            content_type='application/json',
            follow_redirects=True
        )

        response = json.loads(result.get_data())
        assert response.get('sequence_number') is not None
        assert response.get('status_code') == 200
        assert result.status_code == 200

        status_endpoint_result = self.app.get(
            '/status',
            headers={
                'Authorization': 'Bearer ' + token
            },
            query_string={'sequence_number': response.get('sequence_number')},
            follow_redirects=True
        )

        assert json.loads(status_endpoint_result.get_data().decode('utf-8')).get('identity_vault') is True

    @mock.patch('cis_change_service.idp.get_jwks')
    def test_change_endpoint_fails_with_invalid_token_and_jwt_validation_false(self, fake_jwks):
        os.environ['CIS_JWT_VALIDATION'] = 'false'
        f = FakeBearer()
        bad_claims = {
            'iss': 'https://auth-dev.mozilla.auth0.com/',
            'sub': 'mc1l0G4sJI2eQfdWxqgVNcRAD9EAgHib@clients',
            'aud': 'https://hacks',
            'iat': (datetime.utcnow() - timedelta(seconds=3100)).strftime('%s'),
            'exp': (datetime.utcnow() - timedelta(seconds=3100)).strftime('%s'),
            'scope': 'read:allthething',
            'gty': 'client-credentials'
        }
        fh = open('tests/fixture/valid-profile.json')
        user_profile = json.loads(fh.read())
        fh.close()
        user_profile = user_profile
        fake_jwks.return_value = json_form_of_pk
        token = f.generate_bearer_with_scope('read:profile', bad_claims)
        api.app.testing = True
        self.app = api.app.test_client()
        result = self.app.get(
            '/change',
            headers={
                'Authorization': 'Bearer ' + token
            },
            data=json.dumps(user_profile),
            content_type='application/json',
            follow_redirects=True
        )

        assert result.status_code == 200

    def teardown_class(self):
        subprocess.Popen(['killall', 'node'])
