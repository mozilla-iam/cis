# Debugging CIS

## Common issues

### I need to diagnose a missing user or wrong attributes for a user

You'll want to look at the CIS Publisher logs for this.

You'll want to look at CloudWatch logs for their `user_id`, for example go to https://us-west-2.console.aws.amazon.com/cloudwatch/home?region=us-west-2#logEventViewer:group=/aws/lambda/ldap-publisher-production-handler for the LDAP Publisher (production) and enter "ad|Mozilla-LDAP|someonehere" in the filter field.

Look for any message that starts with `WARNING`, `ERROR` or `CRITICAL`.

If an error message contains an HTTP API reply with an error (such as `HTTP 500` error or something more explicit), this means an API denied the request. In general, this is going to be indicate as well in the error message and is probably Person or Change API.
Go to the relevant API logs (Person or Change) and perform a similar search, or search for the same date range.

### I still don't know what's happening, how to I find source data for users?

#### LDAP
Source data for LDAP users is stored as a JSON file in S3, look for `ldap` buckets. Here's an example way to parse them:
```
unxz ldap-full...json.xz
python
>>> import json
>>> x = json.load(open('ldap-full...json'))
>>> [x[z] for z in x if z == 'mail=somewhere@mozilla.com,o=com,dc=mozilla']
```
Do not forget to wipe the data after you're done.

#### HRIS
Source data for HRIS is not stored. You can find the URL to the HRIS report encrypted in the configuration with it's credentials. Currently, this is in SSM.

## Tips and tricks with AWS

### Get a user from a table in CIS Vault

```
# Full user
aws dynamodb get-item --table-name testing-identity-vault --key '{"id": {"S": "ad|Mozilla-LDAP|gdestuynder"}}'

# Just a field (its a bit convoluted..)
aws dynamodb get-item --table-name testing-identity-vault --key '{"id": {"S": "ad|Mozilla-LDAP|gdestuynder"}}'|jq '.Item.profile.S'|sed 's/\\//g'|sed 's/^"\|$"//'|jq '.user_id'

# Get all field names for a list of values like `staff_information`
aws dynamodb get-item --table-name testing-identity-vault --key '{"id": {"S": "ad|Mozilla-LDAP|gdestuynder"}}'|jq '.Item.profile.S'|sed 's/\\//g'|sed 's/^"\|$"//'|jq '.staff_information | .[] | .value' 
```

### Run a Lambda publisher function for a specific user (instead of all users)

```
aws lambda invoke --function-name hris-publisher-testing-handler:\$LATEST --payload '["ad|Mozilla-LDAP|gdestuynder"]' --log-type Tail /dev/stdout 
```

### Stream CloudWatch logs

```
# Install SAW first (https://github.com/TylerBrock/saw)

# Find a log "file"
saw groups |grep profile

# "tail" a cloudwatch log
saw swatch /aws/lambda/change-service-testing-api
```

### SSM

Be careful with this one!
```
# Override a secret
aws ssm put-parameter --overwrite --type SecureString --name /iam/cis/development/hris_publisher/hris --value 'YOUR VALUE
HERE'
```

```
# Get a param
aws ssm get-parameter --name /iam/cis/testing/hris_publisher/hris
```

```
# List available params
aws ssm get-parameters-by-path --path /iam/cis/
```

## Key / Crypto issues

1. Verify the key you verify with is correct in the well-known endpoint (e.g.
   https://auth.mozilla.com/.well-known/mozilla-iam).
2. Verify the JWS string can be verified, you can use https://jwt.io/ for example (it's browser-side) and paste the JWS
   + the correct public JWKS from the above endpoint. It should say verification successful.
3. Ensure the Lambda function is not using cache (if you want to be sure, re-deploy it).

If needed, you can use the python script present in `cis/well-known-endpoint/pem_to_jwks.py` to convert PEM to JWKS
