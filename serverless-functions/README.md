# Serverless function handlers

# How is it setup?

Each function is a very simple handle/wrapper around a module that is located in the `/cis/python-modules` directory of
this project. Functions are meant to be kept as simple as possible, where all the logic goes into the python module.

# How do you test live functions?

## Deploy

`make STAGE=development deploy-ldap-publisher`

NOTE: If you changed the python-modules you'll need to update the Lambda layers as such:
```
cd ..
make STAGE=development build
```

NOTE: You can deploy all functions at once as well if you wish:
```
cd ..
make STAGE=development release
```


## Invoke

`aws lambda invoke --function-name ldap-publisher-development-handler:\$LATEST --payload '["ad|Mozilla-LDAP|gdestuynder"]' --log-type Tail /dev/stdout`

## Watch logs

`saw watch /aws/lambda/ldap-publisher-development-handler`

## About SSM parameter (secrets)

Most parameters are in the namespace dedicated to the function, such as
`/iam/cis/{lambda,..}/{development,testing,production}/function_name_here/*`
However, some may be available to all functions as well (ie not within a `function_name_here` namespace).

Warning: copy pasting certain type of data to the web console or through AWS CLI may add unwanted quoting to the
variables, making them non-functional (e.g. if the code tries to load json, but it's double-quoted). Make sure you have
variables that your or existing code will be able to parse!

### Example
Add them:

```
export env=development
for i in ldap hris access_provider cis mozilliansorg;do
  echo "Enter secret for: $i"
  read s
  aws ssm put-parameter --overwrite --type SecureString --name /iam/cis/$env/keys/${i} --value $s
  unset s
done
```

Remove them:
```
export env=development
for i in ldap hris access_provider cis mozilliansorg;do
  echo "Deleting $i..."
  aws ssm delete-parameter --name /iam/cis/$env/keys/${i}
done
```

## Protips to convert PEM to JWK (for keys)

Because you know you want to, sometimes.

- Install nodejs if you somehow don't have it
- Install https://www.npmjs.com/package/rsa-pem-to-jwk

TLDR:
```
npm install rsa-pem-to-jwk
var fs = require('fs');
var rsaPemToJwk = require('rsa-pem-to-jwk');

# private or public, depending what key you need
JSON.stringify(rsaPemToJwk(fs.readFileSync('privateKey.pem'), {use: 'sig'}, 'private'));
```
