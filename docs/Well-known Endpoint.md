# Well-known endpoint

The well-known endpoint is defined by [RFC 5785](https://www.ietf.org/rfc/rfc5785.txt).
It is used for simple resource discovery related to Mozilla IAM. It is not an OpenID Connect endpoint or openid
compliant discovery URI.

The endpoint path for CIS is `/.well-known/mozilla-iam`.

- Production endpoint: <https://auth.mozilla.com/.well-known/mozilla-iam>.
- Development endpoint: <https://auth.allizom.org/.well-known/mozilla-iam>.

## .well-known/mozilla-iam specification

**Content-Type:** application/json

JSON examples: [here](../well-known-endpoint/tpl)

Relevant fields:

- `oidc_discovery_uri` is a pointed to the OpenID Connect discovery well-known URI.
- `access_file` contains the access file information, which itself contains public authorization data for users, groups,
  RPs.
- `access_file.endpoint` the actual endpoint to query. It returns a YAML formatted document.
- `access_file.jwks.keys` a list of valid public keys and their algorithms. These keys are used to verify the signature
  of the `access_file.endpoint` file. The signature is built-in the file.
- `access_file.aai_mappings` contains Authenticator Assurance Indicators, such as "used 2FA to authenticate".
  Follows the [Mozilla Standard Levels](https://infosec.mozilla.org/guidelines/risk/standard_levels).
- `api` contains the CIS Person-API information, which is used to query or insert data in CIS databases.
- `api.endpoint` is the actual endpoint.
- `api.publishers_supported` is a list of publishers supported by the Person-API endpoint. These are entities which may
  insert data in CIS databases.
- `api.publishers_jwks.keys` are the list of valid public keys for a specific publisher. These are used
  to verify the CIS user profile signature for publishers. See also
[cis_profile/profile.schema](../python-modules/cis_profile/cis_profile/data/profile.schema)
  for a list of supported publishers.
- `api.profile_*schema*_uri`: URI to various supported Person-API schemas. All data stored by Person-API
  validates with these schemas.
- `scopes_supported`: the scopes supported by the Person-API OAuth2 authorizer.

## JWKS

JWKS are the keys for JWS (JSON Web Signature) keys. This is where you find the public keys to verify the signatures
of tokens, files signed in this way.

A JWS is a base64 encoded, serialized JSON document with a signature appended at the end of the string. When decoded and
verified, the result is a JSON document.

Note that this mean that it does not provide "detached" signatures natively (to do so you'd need to hash some content,
then make a JWS with the hash, and manually do the hash verification, which would also be fine as long as you agree on a
hash algorithm between the provider and consumers of the JWS and it's associated, detached content).


See also: <https://tools.ietf.org/html/rfc7517> for a specification of the format and all used fields.

### Key generation for JWKS notes

JWKS are simply base64 encoded PEM formatted keys (PEM is stored in `jwks.keys.x5c`).
You can generate one as such:

```
# Private key
$ openssl genrsa | tee private_key.pem | base64 > jwks_private_key.key

# Public key
$ openssl rsa -in private_key.pem -pubout | tee public_key.pem | base64 > jwks_public_key.key
```

The files in the example above, `jwks_private_key.key` and `jwks_private_key.key` can then directly be loaded, decoded
and used by most JWS libraries. Note: never expose the private key to the public.

## .well-known/mozilla-iam-publisher-rules specification

This file governs the rules by which a publisher is allowed to change user profile data. If this file is fetched as
source of truth, it's signature must be verified similarly to the `access_file` (see "Security notes" below)
Otherwise, it is considered to be informational only and the system of records (CIS) keeps an authoritative copy.

**Content-Type:** application/json

JSON examples: [here](../well-known-endpoint/tpl)

Relevant fields:

- `create` represents arrays of publishers which are allowed to write to profile attributes that are `null`.
- `update` represents single, unique publishers which are allowed to update fields which are not `null`.
- `display` represents DinoPark's user display intent, i.e. a setting the user can change to communicate their intent on
  how to display the data in DinoPark. This allow a user to "show their name publicly, or not" for example.

Note that `{create,update,display}.access_information`, `identities`, `staff_information` are structures with childs (2
level deep).

Relevant values:
- `_default_` indicates that this default will be used for all fields that are not specifically named in the rule file.

See also the [Profiles.md](Profiles.md) document for more information on profile fields.

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
