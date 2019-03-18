# Debugging CIS

## Tips and tricks with AWS

### Get a user from a table in CIS Vault

```
# Full user
aws dynamodb get-item --table-name testing-identity-vault --key '{"id": {"S": "ad|Mozilla-LDAP|gdestuynder"}}'

# Just a field (its a bit convoluted..)
aws dynamodb get-item --table-name testing-identity-vault --key '{"id": {"S": "ad|Mozilla-LDAP|gdestuynder"}}'|jq '.Item.profile.S'|sed 's/\\//g'|sed 's/^"\|$"//'|jq '.user_id'
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
