import boto3
import logging
import os

from botocore.stub import Stubber
from datetime import datetime, timedelta

from moto import mock_dynamodb2
from moto import mock_kinesis
from moto import mock_sts

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)


class TestConnect(object):
    def test_connect_object_init(self):
        from cis_aws import connect
        c = connect.AWS()
        assert c is not None

    def test_botocore_client_initialization(self):
        from cis_aws import connect
        c = connect.AWS()
        tested_session = c.session(region_name='us-east-1')
        assert tested_session is not None

    def test_botocore_client_initialization_without_region(self):
        from cis_aws import connect
        c = connect.AWS()
        tested_session = c.session()
        assert tested_session is not None
        assert tested_session.region_name == 'us-west-2'

    def test_botocore_client_returns_session_if_inited(self):
        from cis_aws import connect
        c = connect.AWS()
        tested_session = c.session(region_name='eu-west-1')
        c._boto_session = Stubber(boto3.session.Session(
            region_name='eu-west-1'
        )).client

        tested_session = c.session()
        assert tested_session == c._boto_session

    @mock_sts
    def test_assume_role(self):
        ROLE_ARN = 'arn:aws:iam::123456789000:role/demo-assume-role'
        from cis_aws import connect
        c = connect.AWS()

        # Stub around the session because we are not testing sessions.
        c._boto_session = Stubber(boto3.session.Session(
            region_name='us-west-2'
        )).client

        result = c.assume_role(ROLE_ARN)

        assert result['Credentials']['AccessKeyId'] is not None
        assert result['Credentials']['SecretAccessKey'] is not None
        assert result['Credentials']['SessionToken'] is not None
        assert result['Credentials']['Expiration'] is not None
        assert result['AssumedRoleUser']['Arn'] is not None

    @mock_sts
    def test_assume_role_expiry(self):
        from cis_aws import connect
        c = connect.AWS()
        ROLE_ARN = 'arn:aws:iam::123456789000:role/demo-assume-role'
        from cis_aws import connect
        c = connect.AWS()

        # Stub around the session because we are not testing sessions.
        c._boto_session = Stubber(boto3.session.Session(
            region_name='us-west-2'
        )).client

        result = c.assume_role(ROLE_ARN)
        assert result is not None

        os.environ['CIS_ENVIRONMENT'] = 'TESTING'
        assert c._assume_role_is_expired() is False
        an_hour_ago = datetime.utcnow() - timedelta(minutes=61)
        c.assume_role_session['Credentials']['Expiration'] = an_hour_ago
        assert c._assume_role_is_expired() is True

        # Test local always returns False
        os.environ['CIS_ENVIRONMENT'] = 'local'
        assert c._assume_role_is_expired() is False

        # Test local always returns False
        os.environ['CIS_ENVIRONMENT'] = 'LoCaL'
        assert c._assume_role_is_expired() is False

        # Test local always returns False
        os.environ['CIS_ENVIRONMENT'] = 'LOCAL'
        assert c._assume_role_is_expired() is False

    def test_discover_cis_environment(self):
        from cis_aws import connect
        c = connect.AWS()

        # Test default fall through to local environ
        assert c._discover_cis_environment() == 'local'

        # Test custom environment name
        os.environ['CIS_ENVIRONMENT'] = 'purple'
        assert c._discover_cis_environment() == 'purple'

    @mock_dynamodb2
    @mock_sts
    def test_discover_dynamodb_table_local(self):
        os.environ['CIS_ENVIRONMENT'] = 'local'
        name = 'local-identity-vault'
        conn = boto3.client('dynamodb',
                            region_name='us-west-2',
                            aws_access_key_id="ak",
                            aws_secret_access_key="sk")

        conn.create_table(
            TableName=name,
            KeySchema=[
                {'AttributeName': 'id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'id', 'AttributeType': 'S'}
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5
            }
        )

        table_description = conn.describe_table(TableName=name)
        arn = table_description['Table']['TableArn']

        tags = [
            {'Key': 'cis_environment', 'Value': 'unittest'},
            {'Key': 'application', 'Value': 'identity-vault'}
        ]
        conn.tag_resource(ResourceArn=arn, Tags=tags)

        from cis_aws import connect
        c = connect.AWS()

        res = c._discover_dynamo_table(conn)
        assert res is not None

    @mock_dynamodb2
    def test_discover_dynamodb_table_mock_cloud(self):
        os.environ['CIS_ENVIRONMENT'] = 'testing'
        name = 'testing-identity-vault'
        conn = boto3.client('dynamodb',
                            region_name='us-east-1',
                            aws_access_key_id="ak",
                            aws_secret_access_key="sk")

        conn.create_table(
            TableName=name,
            KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        )

        table_description = conn.describe_table(TableName=name)
        arn = table_description['Table']['TableArn']

        assert arn is not None

        waiter = conn.get_waiter('table_exists')
        waiter.wait(
            TableName='testing-identity-vault',
            WaiterConfig={
                'Delay': 100,
                'MaxAttempts': 100
            }
        )

        tags = [
            {'Key': 'cis_environment', 'Value': 'testing'},
            {'Key': 'application', 'Value': 'identity-vault'}
        ]
        conn.tag_resource(ResourceArn=arn, Tags=tags)
        from cis_aws import connect
        c = connect.AWS()

        res = c._discover_dynamo_table(conn)
        assert res is not None
        assert res.endswith('testing-identity-vault')

    @mock_kinesis
    def test_discover_kinesis_stream_local(self):
        os.environ['CIS_ENVIRONMENT'] = 'local'
        name = 'local-stream'
        conn = boto3.client('kinesis',
                            region_name='us-east-1',
                            aws_access_key_id="ak",
                            aws_secret_access_key="sk")

        response = conn.create_stream(
            StreamName=name,
            ShardCount=1
        )

        waiter = conn.get_waiter('stream_exists')

        waiter.wait(
            StreamName=name,
            Limit=100,
            WaiterConfig={
                'Delay': 100,
                'MaxAttempts': 5
            }
        )

        tags_1 = {'Key': 'cis_environment', 'Value': 'local'}
        tags_2 = {'Key': 'application', 'Value': 'change-stream'}
        conn.add_tags_to_stream(StreamName=name, Tags=tags_1)
        conn.add_tags_to_stream(StreamName=name, Tags=tags_2)

        assert response is not None

        from cis_aws import connect
        c = connect.AWS()

        result = c._discover_kinesis_stream(conn)
        assert result is not None
        assert result.endswith(name)

    @mock_kinesis
    def test_discover_kinesis_mock_cloud(self):
        os.environ['CIS_ENVIRONMENT'] = 'testing'
        name = 'testing-stream'
        conn = boto3.client('kinesis',
                            region_name='us-east-1',
                            aws_access_key_id="ak",
                            aws_secret_access_key="sk")

        response = conn.create_stream(
            StreamName=name,
            ShardCount=1
        )

        waiter = conn.get_waiter('stream_exists')

        waiter.wait(
            StreamName=name,
            Limit=100,
            WaiterConfig={
                'Delay': 100,
                'MaxAttempts': 5
            }
        )

        tags_1 = {'cis_environment': 'testing'}
        tags_2 = {'application': 'change-stream'}
        conn.add_tags_to_stream(StreamName=name, Tags=tags_1)
        conn.add_tags_to_stream(StreamName=name, Tags=tags_2)

        assert response is not None

        from cis_aws import connect
        c = connect.AWS()

        result = c._discover_kinesis_stream(conn)
        assert result is not None
        assert result.endswith(name)

    @mock_dynamodb2
    @mock_sts
    def test_dynamodb_full_client_with_mock_cloud(self):
        os.environ['CIS_ENVIRONMENT'] = 'testing'
        name = 'testing-identity-vault'
        conn = boto3.client('dynamodb',
                            region_name='us-east-1',
                            aws_access_key_id="ak",
                            aws_secret_access_key="sk")

        conn.create_table(
            TableName=name,
            KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        )

        table_description = conn.describe_table(TableName=name)
        arn = table_description['Table']['TableArn']

        assert arn is not None

        waiter = conn.get_waiter('table_exists')
        waiter.wait(
            TableName='testing-identity-vault',
            WaiterConfig={
                'Delay': 100,
                'MaxAttempts': 100
            }
        )

        tags = [
            {'Key': 'cis_environment', 'Value': 'testing'},
            {'Key': 'application', 'Value': 'identity-vault'}
        ]

        conn.tag_resource(ResourceArn=arn, Tags=tags)

        ROLE_ARN = 'arn:aws:iam::123456789000:role/demo-assume-role'
        from cis_aws import connect
        c = connect.AWS()
        c._boto_session = boto3.session.Session(region_name='us-east-1')
        c.assume_role(ROLE_ARN)

        res = c.identity_vault_client()
        assert res is not None

        assert res.get('client') is not None
        assert res.get('arn').endswith('testing-identity-vault')
