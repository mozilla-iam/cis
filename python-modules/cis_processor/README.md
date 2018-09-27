# cis_identity_vault

Contains the code for forming the identity vault dynamodb table streams.

*Usage*

```python
from cis_identity_vault import vault
idv = vault.IdentityVault()
idv.create()
{'TableDescription': {'AttributeDefinitions': [{'AttributeName': 'id', 'AttributeType': 'S'}, {'AttributeName': 'sequence_number', 'AttributeType': 'S'}, {'AttributeName': 'primary_email', 'AttributeType': 'S'}], 'TableName': 'purple-identity-vault', 'KeySchema': [{'AttributeName': 'id', 'KeyType': 'HASH'}], 'TableStatus': 'ACTIVE', 'CreationDateTime': datetime.datetime(2018, 9, 18, 11, 56, 3, 523710, tzinfo=tzlocal()), 'ProvisionedThroughput': {'NumberOfDecreasesToday': 0, 'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}, 'TableSizeBytes': 0, 'ItemCount': 0, 'TableArn': 'arn:aws:dynamodb:us-east-1:123456789011:table/purple-identity-vault', 'LocalSecondaryIndexes': [], 'GlobalSecondaryIndexes': [{'IndexName': 'purple-identity-vault-sequence_number', 'KeySchema': [{'AttributeName': 'sequence_number', 'KeyType': 'HASH'}], 'Projection': {'ProjectionType': 'ALL'}, 'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}}, {'IndexName': 'purple-identity-vault-primary_email', 'KeySchema': [{'AttributeName': 'primary_email', 'KeyType': 'HASH'}], 'Projection': {'ProjectionType': 'ALL'}, 'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}}]}, 'ResponseMetadata': {'RequestId': '2FM9C52TAF4MS3FI3T9HCQJHUGEN37T6RCMX3R1NJ0VS2T2Y6HPV', 'HTTPStatusCode': 200, 'HTTPHeaders': {'Content-Type': 'text/plain', 'server': 'amazon.com', 'x-amzn-requestid': '2FM9C52TAF4MS3FI3T9HCQJHUGEN37T6RCMX3R1NJ0VS2T2Y6HPV'}, 'RetryAttempts': 0}}
idv.tag_vault()
idv.enable_autoscaler()
idv.enable_stream()
```

The above will create an identity vault in your AWS account, tag it, enable NEW_AND_OLD_IMAGES stream, and finally enable autoscaling for the secondary indexes.

The following config parameters should exists in your .mozilla-cis.ini file or as environment variables prefixed with CIS_.

```
#Config parameters

environment=production
region_name=us-west-2
```

Additional supported operations include:

`destroy()` # Deletes the table.
`find_or_create()` # Returns a table resource.
`find()` # Returns an ARN.
