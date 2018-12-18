
import boto3
import json
import logging
import os
import mock
import subprocess
from botocore.stub import Stubber
from boto.kinesis.exceptions import ResourceInUseException
from cis_change_service.common import get_config
from cis_profile import FakeUser
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


class TestProfile(object):
    def setup(self):
        os.environ['CIS_ENVIRONMENT'] = 'local'
        name = 'local-identity-vault'
        os.environ['CIS_CONFIG_INI'] = 'tests/mozilla-cis.ini'
        config = get_config()
        dynalite_port = config('dynalite_port', namespace='cis')
        self.dynaliteprocess = subprocess.Popen(['dynalite', '--port', dynalite_port], preexec_fn=os.setsid)
        conn = boto3.client('dynamodb',
                            region_name='us-west-2',
                            aws_access_key_id="ak",
                            aws_secret_access_key="sk",
                            endpoint_url='http://localhost:{}'.format(dynalite_port))

        kinesalite_port = config('kinesalite_port', namespace='cis')
        kinesalite_host = config('kinesalite_host', namespace='cis')
        self.kinesaliteprocess = subprocess.Popen(['kinesalite', '--port', kinesalite_port], preexec_fn=os.setsid)

        # XXX TBD this will eventually be replaced by logic from the vault module
        # The vault module will have the authoritative definitions for Attributes and GSI
        try:
            conn.create_table(
                TableName=name,
                KeySchema=[
                    {'AttributeName': 'id', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'id', 'AttributeType': 'S'},  # auth0 user_id
                    {'AttributeName': 'sequence_number', 'AttributeType': 'S'},  # sequence number for the last integration
                    {'AttributeName': 'primary_email', 'AttributeType': 'S'},  # value of the primary_email attribute
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
                        'IndexName': '{}-primary_email'.format(name),
                        'KeySchema': [
                            {
                                'AttributeName': 'primary_email',
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
        except Exception as e:
            logger.error('Table error: {}'.format(e))

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
        except Exception as e:
            logger.error('Stream creation error: {}'.format(e))
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
        self.user_profile = FakeUser().as_json()

    @mock.patch('cis_change_service.idp.get_jwks')
    def test_post_a_profile_and_retreiving_status_it_should_succeed(self, fake_jwks):
        from cis_change_service import api
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk
        token = f.generate_bearer_without_scope()
        api.app.testing = True
        self.app = api.app.test_client()
        result = self.app.post(
            '/change',
            headers={
                'Authorization': 'Bearer ' + token
            },
            data=json.dumps(self.user_profile),
            content_type='application/json',
            follow_redirects=True
        )

        response = json.loads(result.get_data())
        sequence_number = response.get('sequence_number')

        # Fake like this went through the stream and skip direct to dynamo to test status endpoint.

        # Profile fields for putting to dynamo
        from cis_change_service import profile

        vault = profile.Vault(sequence_number)
        res = vault.put_profile(self.user_profile)
        assert res['ResponseMetadata']['HTTPStatusCode'] == 200

        # Fetch the sequence number we just inserted to the the vault.
        status_object = profile.Status(sequence_number)
        is_in_vault = status_object.query()

        assert is_in_vault is not None

    @mock.patch('cis_change_service.idp.get_jwks')
    def test_post_profiles_and_retreiving_status_it_should_succeed(self, fake_jwks):
        from cis_change_service import api
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk
        profiles = []
        for x in range(0, 10):
            profiles.append(FakeUser().as_json())
        token = f.generate_bearer_without_scope()
        api.app.testing = True
        self.app = api.app.test_client()
        result = self.app.post(
            '/changes',
            headers={
                'Authorization': 'Bearer ' + token
            },
            data=json.dumps(profiles),
            content_type='application/json',
            follow_redirects=True
        )

        response = json.loads(result.get_data())
        print(response)
        assert 0

    def teardown(self):
        os.killpg(os.getpgid(self.dynaliteprocess.pid), 15)
        os.killpg(os.getpgid(self.kinesaliteprocess.pid), 15)
