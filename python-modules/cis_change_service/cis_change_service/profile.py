"""Get the status of an integration from the identity vault and auth0."""
import json
import random
from cis_aws import connect
from cis_change_service import common
from cis_identity_vault.models import user


class Vault(object):
    """Handles flushing profiles to Dynamo when running local or in stream bypass mode."""
    def __init__(self, sequence_number=None):
        self.connection_object = connect.AWS()
        self.identity_vault_client = None
        self.config = common.get_config()

        if sequence_number is not None:
            self.sequence_number = sequence_number
        else:
            self.sequence_number = random.randrange(0, 10000000000000, 10000)

    def _connect(self):
        self.connection_object.session()
        self.identity_vault_client = self.connection_object.identity_vault_client()
        return self.identity_vault_client

    def put_profile(self, profile_json):
        """Write profile to the identity vault."""
        self._connect()
        user_id = self._get_id(profile_json)

        if isinstance(profile_json, str):
            profile_json = json.loads(profile_json)

        if self.config('dynamodb_transactions', namespace='cis') == 'true':
            profile = user.Profile(
                self.identity_vault_client.get('table'),
                self.identity_vault_client.get('client'),
                transactions=True
            )
        else:
            profile = user.Profile(
                self.identity_vault_client.get('table'),
                self.identity_vault_client.get('client'),
                transactions=False
            )

        user_profile = dict(
            id=profile_json['user_id']['value'],
            primary_email=profile_json['primary_email']['value'],
            sequence_number=self.sequence_number,
            profile=json.dumps(profile_json)
        )

        res = profile.find_or_create(user_profile)
        return res

    def put_profiles(self, profile_list):
        """Write profile to the identity vault."""
        self._connect()
        user_id = self._get_id(profile_json)

        if isinstance(profile_json, str):
            profile_json = json.loads(profile_json)

        if self.config('dynamodb_transactions', namespace='cis') == 'true':
            profile = user.Profile(
                self.identity_vault_client.get('table'),
                self.identity_vault_client.get('client'),
                transactions=True
            )
        else:
            profile = user.Profile(
                self.identity_vault_client.get('table'),
                self.identity_vault_client.get('client'),
                transactions=False
            )

        user_profiles = []

        for profile in profile_list:
            user_profile = dict(
                id=profile_json['user_id']['value'],
                primary_email=profile_json['primary_email']['value'],
                sequence_number=self.sequence_number,
                profile=json.dumps(profile_json)
            )
            user_profiles.append(user_profile)

        return profile.find_or_create_batch(user_profiles)

    def _get_id(self, profile_json):
        if isinstance(profile_json, str):
            profile_json = json.loads(profile_json)
        return profile_json.get('user_id').get('value').lower()

    def _get_primary_email(self, profile_json):
        if isinstance(profile_json, str):
            profile_json = json.loads(profile_json)
        return profile_json.get('primary_email').get('value').lower()


class Status(object):
    """Does the right thing to query if the event was integrated and return the results."""
    def __init__(self, sequence_number):
        self.connection_object = connect.AWS()
        self.identity_vault_client = None
        self.sequence_number = sequence_number

    def _connect(self):
        self.connection_object.session()
        self.identity_vault_client = self.connection_object.identity_vault_client()
        return self.identity_vault_client

    def query(self):
        """Query the identity vault using the named Global Secondary Index for the sequence number."""
        # Vault returns a dictionary of dictionaries for the statuses of each check.
        self._connect()

        client = self.identity_vault_client.get('client')

        result = client.query(
            TableName=self.identity_vault_client.get('arn').split('/')[1],
            IndexName='{}-sequence_number'.format(self.identity_vault_client.get('arn').split('/')[1]),
            Select='ALL_ATTRIBUTES',
            KeyConditionExpression='sequence_number = :sequence_number',
            ExpressionAttributeValues={
                ':sequence_number': {'S': self.sequence_number}
            }
        )

        return result

    @property
    def all(self):
        """Run all checks and return the results for the given sequence number as a dict."""
        return {
            'identity_vault': self.check_identity_vault()
        }

    def check_identity_vault(self):
        """Check the sequence number of the last record put to the identity vault."""
        if self.identity_vault_client is None:
            self._connect()

        query_result = self.query()
        if len(query_result.get('Items')) == 1:
            return True
        else:
            return False
