"""Governs crud operations for profiles in the identity vault.
user_profile must be passed to this in the form required by dynamodb
{
    'id': 'ad|foo',
    'primary_email': 'foo@xyz.com',
    'sequence_number': '123456',
    'profile': 'jsondumpofuserfullprofile'
}
"""
from boto3.dynamodb.conditions import Key


class Profile(object):
    def __init__(self, dynamodb_table_resource):
        """Take a dynamodb table resource to use for operations."""
        self.table = dynamodb_table_resource

    def create(self, user_profile):
        return self.table.put_item(Item=user_profile)

    def update(self, user_profile):
        return self.table.put_item(Item=user_profile)

    def delete(self, user_profile):
        return self.table.delete_item(Item=user_profile)

    def create_batch(self, list_of_profiles):
        # XXX TBD Non MVP Feature
        pass

    def update_batch(self, list_of_profiles):
        # XXX TBD Non MVP Feature
        pass

    def find_by_id(self, id):
        result = self.table.query(
            KeyConditionExpression=Key('id').eq(id)
        )
        return result

    def find_by_email(self, primary_email):
        result = self.table.query(
            IndexName='local-identity-vault-primary_email',
            KeyConditionExpression=Key('primary_email').eq(primary_email)
        )
        return result
