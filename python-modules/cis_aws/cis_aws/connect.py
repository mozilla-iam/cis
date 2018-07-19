import boto3
import logging

from botocore.stub import Stubber
from cis_aws import get_config
from datetime import datetime
from datetime import timedelta


logger = logging.getLogger(__name__)


class AWS(object):
    """
    Contains all the code necessary for role assumption in
    the target AWS account which holds CIS data,
    enumerating dynamodb-tables, and enumerating kinesis streams.
    """
    def __init__(self):
        self.assume_role_session = None
        self._boto_session = None

    def session(self, region_name=None):
        """Return a boto_session in the current account
        in the current region."""
        if region_name is None:
            # Default to us-west-2 if no region provided.
            logger.debug('No region provided.  Defaulting boto session to us-west-2.')
            region_name = 'us-west-2'

        if self._discover_cis_environment() == 'local':
            # If we are running the lib locally return a botocore stub.
            # Must call the .client object in order to return full boto session from Stubber.
            logger.debug('Local environment detected.  Returning boto stub session.')
            self._boto_session = Stubber(boto3.session.Session(region_name=region_name)).client

        if self._boto_session:
            logger.debug('A boto session already exists on the object.  Returning already constructed session.')
            return self._boto_session
        else:
            logger.debug('Initializing new boto session for region: {}'.format(region_name))
            self._boto_session = boto3.session.Session(region_name=region_name)

        return self._boto_session

    def assume_role(self, role_arn=None):
        """Use the boto session in the current account
        to assume a role passed in.
        """
        if self._discover_cis_environment() == 'local':
            self.assume_role_session = {
                'Credentials': {
                    'AccessKeyId': 'FAKEAKIA',
                    'SecretAccessKey': 'FAKEACCESSKEY',
                    'SessionToken': 'FAKESESSIONTOKEN',
                    'Expiration': (datetime.utcnow() + timedelta(hours=1)).replace(tzinfo=None)
                },
                'AssumedRoleUser': {
                    'AssumedRoleId': 'FAKEID',
                    'Arn': 'arn:aws:iam::123456789000:role/demo-assume-role'
                },
                'PackedPolicySize': 123
            }
            return self.assume_role_session

        if self.assume_role_session is not None and self._assume_role_is_expired() is False:
            return self.assume_role_session

        # If the role arn is none get it from the config store.
        if role_arn is None:
            config = get_config()
            role_arn = config('assume_role_arn', namespace='cis').lower()

        sts = self._boto_session.client('sts')

        res = sts.assume_role(
            DurationSeconds=3600,
            RoleArn=role_arn,
            RoleSessionName='cis-aws-library',
        )

        self.assume_role_session = res
        return res

    def identity_vault_client(self):
        """Discover DynamoDb table for the environment.
        Return a dictionary with a client and database arn"""
        self._check_sessions_exist()
        if self._discover_cis_environment() == 'local':
            # Assume we are using dynalite and setup for that
            config = get_config()
            dynalite_port = config('dynalite_port', namespace='cis', default='4567')
            dynalite_host = config('dynalite_host', namespace='cis', default='localhost')

            # Initialize a dynamodb client pointed at the dynalite endpoint
            dynamodb_client = self._boto_session.client(
                'dynamodb', endpoint_url='http://{}:{}'.format(dynalite_host, dynalite_port)
            )

            # Construct a dictionary of standard information.
            identity_vault_info = {
                'client': dynamodb_client,
                'arn': self._discover_dynamo_table(dynamodb_client)
            }
        else:
            # Assume we are using an assumeRole because not local.
            dynamodb_client = self._boto_session.client(
                'dynamodb',
                aws_access_key_id=self.assume_role_session['Credentials']['AccessKeyId'],
                aws_secret_access_key=self.assume_role_session['Credentials']['SecretAccessKey'],
                aws_session_token=self.assume_role_session['Credentials']['SessionToken']
            )
            identity_vault_info = {
                'client': dynamodb_client,
                'arn': self._discover_dynamo_table(dynamodb_client)
            }

        return identity_vault_info

    def input_stream_client(self):
        """Discover the input stream ARN for the cis_environment.
        Return a dictionary containing a kinesis client and the stream arn."""
        self._check_sessions_exist()
        if self._discover_cis_environment() == 'local':
            # Assume we are using dynalite and setup for that
            config = get_config()
            kinesalite_port = config('kinesalite_port', namespace='cis', default='4567')
            kinesalite_host = config('kinesalite_host', namespace='cis', default='localhost')

            # Initialize a kinesis client pointed at the kinesalite endpoint
            kinesis_client = self._boto_session.client(
                'kinesis', endpoint_url='http://{}:{}'.format(kinesalite_host, kinesalite_port)
            )

            # Construct a dictionary of standard information.
            stream_info = {
                'client': kinesis_client,
                'arn': self._discover_kinesis_stream(kinesis_client)
            }
        else:
            # Assume we are using an assumeRole because not local.
            kinesis_client = self._boto_session.client(
                'kinesis',
                aws_access_key_id=self.assume_role_session['Credentials']['AccessKeyId'],
                aws_secret_access_key=self.assume_role_session['Credentials']['SecretAccessKey'],
                aws_session_token=self.assume_role_session['Credentials']['SessionToken']
            )

            stream_info = {
                'client': kinesis_client,
                'arn': self._discover_kinesis_stream(kinesis_client)
            }

        return stream_info

    def _check_sessions_exist(self):
        if self._discover_cis_environment() == 'local':
            logger.info('CIS Local environment detected skipping cloud based validations.')
        if self._boto_session is not None and self.assume_role_session is not None:
            logger.info('Boto3 session object and assumeRole exists proceeding to next check.')
        else:
            logger.error('You must initialize an assumeRole and boto session.')
            raise ValueError('AssumeRole or Boto3 Session not initialized.  Refusing operation.')

    def _assume_role_is_expired(self):
        if self.assume_role_session is None:
            return True

        if self._discover_cis_environment() == 'local':
            return False

        expiry = self.assume_role_session['Credentials']['Expiration']
        now = datetime.utcnow()

        if expiry.replace(tzinfo=None) > now.replace(tzinfo=None):
            return False
        else:
            return True

    def _discover_cis_environment(self):
        """Use everett config manager to determine the environment we are in."""
        config = get_config()
        result = config('environment', namespace='cis', default='local').lower()
        return result

    def _discover_kinesis_stream(self, kinesis_client):
        """Enumerate all kinesis streams in the region for the current
        assumeRole.  Return the stream arn matching the appropriate tagging
        configuration."""
        if self._discover_cis_environment() == 'local':
            # Assume developer environment and return for an explicit stream name.
            return kinesis_client.describe_stream(StreamName='local-stream')['StreamDescription']['StreamARN']

        else:
            # Assume we are in AWS and list streams, describe streams, and check tags.
            streams = kinesis_client.list_streams(Limit=100)

            for stream in streams.get('StreamNames'):
                tags = kinesis_client.list_tags_for_stream(
                    StreamName=stream
                ).get('Tags')

                for tag in tags:
                    if tag.get('Key') == 'cis_environment' and tag.get('Value') == self._discover_cis_environment():
                        return kinesis_client.describe_stream(StreamName=stream)['StreamDescription']['StreamARN']
                    else:
                        continue
            return None

    def _discover_dynamo_table(self, dynamodb_client):
        """Enumerate all tables in a region for the current
        assumerole session.  Return the arn of table matching the
        appropriate tagging configuration."""

        if self._discover_cis_environment() == 'local':
            # Assume that the local identity vault is always called local-identity-vault
            return dynamodb_client.describe_table(TableName='local-identity-vault')['Table']['TableArn']
        else:
            # Assume that we are in AWS and list tables, describe tables, and check tags.
            tables = dynamodb_client.list_tables(
                Limit=100
            )

            for table in tables.get('TableNames'):
                table_arn = dynamodb_client.describe_table(TableName=table)['Table']['TableArn']
                tags = dynamodb_client.list_tags_of_resource(ResourceArn=table_arn).get('Tags', [])

                for tag in tags:
                    if tag.get('Key') == 'cis_environment' and tag.get('Value') == self._discover_cis_environment():
                        return table_arn
                    else:
                        continue
            return None
