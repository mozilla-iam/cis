"""Get the status of an integration from the identity vault and auth0."""
import json
from cis_aws import connect


class Vault(object):
    """Handles flushing profiles to Dynamo when running local or in stream bypass mode."""
    def __init__(self, sequence_number):
        self.connection_object = connect.AWS()
        self.identity_vault_client = None
        self.sequence_number = sequence_number

    def _connect(self):
        self.connection_object.session()
        self.connection_object.assume_role()
        self.identity_vault_client = self.connection_object.identity_vault_client()
        return self.identity_vault_client

    def put_profile(self, profile_json):
        """Write profile to the identity vault."""
        if self.identity_vault_client is None:
            self._connect()

        user_id = self._get_id(profile_json)
        primary_email = self._get_primary_email(profile_json)
        dynamodb_schema_dict = {
            'profile': {'S': json.dumps(profile_json)},
            'id': {'S': user_id},
            'sequence_number': {'S': self.sequence_number},
            'primaryEmail': {'S': primary_email}
        }

        client = self.identity_vault_client.get('client')
        res = client.put_item(
            TableName=self.identity_vault_client.get('arn').split('/')[1],
            Item=dynamodb_schema_dict
        )

        return res

    def _get_id(self, profile_json):
        return profile_json.get('user_id').get('value').lower()

    def _get_primary_email(self, profile_json):
        return profile_json.get('primary_email').get('value').lower()


class Status(object):
    """Does the right thing to query if the event was integrated and return the results."""
    def __init__(self, sequence_number):
        self.connection_object = connect.AWS()
        self.identity_vault_client = None
        self.sequence_number = sequence_number

    def _connect(self):
        self.connection_object.session()
        self.connection_object.assume_role()
        self.identity_vault_client = self.connection_object.identity_vault_client()
        return self.identity_vault_client

    def query(self):
        """Query the identity vault using the named Global Secondary Index for the sequence number."""
        # Vault returns a dictionary of dictionaries for the statuses of each check.
        if self.identity_vault_client is None:
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
