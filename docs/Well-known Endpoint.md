# Well-known endpoint

The well-known endpoint is defined by [RFC 5785](https://www.ietf.org/rfc/rfc5785.txt).
It is used for simple resource discovery related to Mozilla IAM. It is not an OpenID Connect endpoint or openid
compliant discovery URI.

The endpoint path for CIS is `/.well-known/mozilla-iam`.

- Production endpoint: <https://auth.mozilla.com/.well-known/mozilla-iam>.
- Development endpoint: <https://auth.allizom.org/.well-known/mozilla-iam>.

## .well-known/mozilla-iam specification

**Content-Type:** application/json

JSON example: [mozilla-iam.json](.well-known/mozilla-iam.json)

Relevant fields:

- `oidc_discovery_uri` is a pointed to the OpenID Connect discovery well-known URI.
- `access_file` contains the access file information, which itself contains public authorization data for users, groups,
  RPs.
- `access_file.endpoint` the actual endpoint to query. It returns a YAML formatted document.
- `access_file.jwks_keys` a list of valid public keys and their algorithms. These keys are used to verify the signature
  of the `access_file.endpoint` file. The signature is built-in the file.
- `person-api` contains the CIS Person-API information, which is used to query or insert data in CIS databases.
- `person-api.endpoint` is the actual endpoint.
- `person-api.publishers_supported` is a list of publishers supported by the Person-API endpoint. These are entities which may
  insert data in CIS databases.
- `person-api.publishers_supported.jwks_keys` are the list of valid public keys for a specific publisher. These are used
  to verify the CIS user profile signature for publishers.
- `person-api.profile_*schema*_uri`: URI to various supported Person-API schemas. All data stored by Person-API
  validates with these schemas.
- `scopes_supported`: the scopes supported by the Person-API OAuth2 authorizer.

## JWKS

JWKS are the keys for JWT (JSON Web Token) signing. This is where you find the public keys to verify the signatures
of tokens, files signed in this way.

A JWT is a base64 encoded, serialized JSON document with a signature appended at the end of the string. When decoded and
verified, the result is a JSON document.

Note that this mean that it does not provide "detached" signatures natively (to do so you'd need to hash some content,
then make a JWT with the hash, and manually do the hash verification, which would also be fine as long as you agree on a
hash algorithm between the provider and consumers of the JWT and it's associated, detached content).

### Key generation for JWKS notes

JWKS are simply base64 encoded PEM formatted keys.
You can generate one as such:

```
# Private key
$ openssl genrsa | tee private_key.pem | base64 > jwks_private_key.key

# Public key
$ openssl rsa -in private_key.pem -pubout | tee public_key.pem | base64 > jwks_public_key.key
```

The files in the example above, `jwks_private_key.key` and `jwks_private_key.key` can then directly be loaded, decoded
and used by most JWT libraries. Note: never expose the private key to the public.

## Security notes

1. As the well-known file `mozilla-iam` is the source of truth for keys, it *must* be rechecked regularly in case keys are
rotated. This file should be fetched at least once every 24h. It is recommended to fetch it every 15 minutes.

2. Any of the keys in the list keys `jwks_keys` may be used to sign. This means you have to attempt to validate with
   every key listed until one of them succeeds or all of them fail. This is useful to smoothly rotate keys (this means
there is rarely more than 2 public keys listed in `jwks_keys` and usually only 1 key is listed.

3. As this well-known file `mozilla-iam` is the source of truth for keys, it also mean that it may not be tampered with.
   This file can be asserted valid by validating the HTTPS connection - however, it is also manually signed should you
want to verify it out of band. You can find the signed version at `https://auth.mozilla.com/.well-known/mozilla-iam.asc`
which is a GnuPG signed file by the [Mozilla Enterprise Information Security
key](https://gpg.mozilla.org/pks/lookup?search=infosec%40mozilla.com&op=vindex). This key is itself signed by several
Mozilla staff members.
