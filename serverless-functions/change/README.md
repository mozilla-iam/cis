# Change

## About SSM parameter (secrets)

Add them:

```
env=development
for i in ldap hris access_provider cis mozilliansorg;do
  echo "Enter secret for: $i"
  read s
  aws ssm put-parameter --overwrite --type SecureString --name /iam/cis/$env/keys/${i} --value $s
  unset s
done
```

Remove them:
```
env=development
for i in ldap hris access_provider cis mozilliansorg;do
  echo "Deleting $i..."
  aws ssm delete-parameter --name /iam/cis/$env/keys/${i}
done
```

## Protips to convert PEM to JWK

Because you know you want to.

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
