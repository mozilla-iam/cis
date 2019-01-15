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
    def __init__(
        self,
        dynamodb_table_resource=None,
        dynamodb_client=None,
        transactions=True
    ):
        """Take a dynamodb table resource to use for operations."""
        self.table = dynamodb_table_resource
        self.client = dynamodb_client
        self.transactions = transactions

    def _run_transaction(self, transact_items):
        response = self.client.transact_write_items(
            TransactItems=transact_items,
            ReturnConsumedCapacity='TOTAL',
            ReturnItemCollectionMetrics='SIZE'
        )
        return response

    def create(self, user_profile):
        if self.transactions:
            res = self._create_with_transaction(user_profile)
        else:
            res = self._create_without_transaction(user_profile)
        return res

    def _create_without_transaction(self, user_profile):
        return self.table.put_item(Item=user_profile)

    def _create_with_transaction(self, user_profile):
        transact_items = {
            'Put': {
                'Item': {
                    'id': {
                        'S': user_profile['id']
                    },
                    'profile': {
                        'S': user_profile['profile']
                    },
                    'primary_email': {
                        'S': user_profile['primary_email']
                    },
                    'sequence_number': {
                        'S': user_profile['sequence_number']
                    }
                },
                'ConditionExpression': 'attribute_not_exists(id)',
                'TableName': self.table.name,
                'ReturnValuesOnConditionCheckFailure': 'NONE'
            }
        }

        return self._run_transaction([transact_items])

    def update(self, user_profile):
        if self.transactions:
            res = self._update_with_transaction(user_profile)
        else:
            res = self._update_without_transaction(user_profile)
        return res

    def _update_with_transaction(self, user_profile):
        transact_items = {
            'Update': {
                'Key': {
                    'id': {'S': user_profile['id']}
                },
                'ExpressionAttributeValues': {
                    ':p': {
                        'S': user_profile['profile']
                    },
                    ':pe': {
                        'S': user_profile['primary_email']
                    },
                    ':sn': {
                        'S': user_profile['sequence_number']
                    }
                },
                'ConditionExpression': 'attribute_exists(id)',
                'UpdateExpression': 'SET profile = :p, primary_email = :pe, sequence_number = :sn',
                'TableName': self.table.name,
                'ReturnValuesOnConditionCheckFailure': 'NONE'
            }
        }

        return self._run_transaction([transact_items])

    def _update_without_transaction(self, user_profile):
        return self.table.put_item(Item=user_profile)

    def delete(self, user_profile):
        if self.transactions:
            res = self._delete_with_transaction(user_profile)
        else:
            res = self._delete_without_transaction(user_profile)
        return res

    def _delete_with_transaction(self, user_profile):
        transact_items = {
            'Delete': {
                'Key': {
                    'id': {'S': user_profile['id']}
                },
                'ConditionExpression': 'attribute_exists(id)',
                'TableName': self.table.name,
                'ReturnValuesOnConditionCheckFailure': 'NONE'
            }
        }

        return self._run_transaction([transact_items])

    def _delete_without_transaction(self, user_profile):
        return self.table.delete_item(Item=user_profile)

    def create_batch(self, list_of_profiles):
        transact_items = []
        for user_profile in list_of_profiles:
            transact_item = {
                'Put': {
                    'Item': {
                        'id': {
                            'S': user_profile['id']
                        },
                        'profile': {
                            'S': user_profile['profile']
                        },
                        'primary_email': {
                            'S': user_profile['primary_email']
                        },
                        'sequence_number': {
                            'S': user_profile['sequence_number']
                        }
                    },
                    'ConditionExpression': 'attribute_not_exists(id)',
                    'TableName': self.table.name,
                    'ReturnValuesOnConditionCheckFailure': 'NONE'
                }
            }
            transact_items.append(transact_item)
        return self._run_transaction(transact_items)

    def update_batch(self, list_of_profiles):
        transact_items = []
        for user_profile in list_of_profiles:
            transact_item = {
                'Update': {
                    'Key': {
                        'id': {'S': user_profile['id']}
                    },
                    'ExpressionAttributeValues': {
                        ':p': {
                            'S': user_profile['profile']
                        },
                        ':pe': {
                            'S': user_profile['primary_email']
                        },
                        ':sn': {
                            'S': user_profile['sequence_number']
                        }
                    },
                    'ConditionExpression': 'attribute_exists(id)',
                    'UpdateExpression': 'SET profile = :p, primary_email = :pe, sequence_number = :sn',
                    'TableName': self.table.name,
                    'ReturnValuesOnConditionCheckFailure': 'NONE'
                }
            }
            transact_items.append(transact_item)
        return self._run_transaction(transact_items)

    def find_by_id(self, id):
        result = self.table.query(
            KeyConditionExpression=Key('id').eq(id)
        )
        return result

    def find_by_email(self, primary_email):
        result = self.table.query(
            IndexName='{}-primary_email'.format(self.table.table_name),
            KeyConditionExpression=Key('primary_email').eq(primary_email)
        )
        return result

    @property
    def all(self):
        response = self.table.scan()
        users = response.get('Items')
        while 'LastEvaluatedKey' in response:
            response = self.table.scan(
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            users.extend(response['Items'])
        return users

    def all_by_page(self, next_page=None, limit=25):
        if next_page is not None:
            response = self.table.scan(
                Limit=limit,
                ExclusiveStartKey=next_page
            )
        else:
            response = self.table.scan(
                Limit=limit
            )
        return response
