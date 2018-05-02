# User Profiles (v2)

This document describes the Mozilla IAM user profiles version 2.

IAM Goals:
- Data structures drives API design
- Must provide structures that allow to generate backward-compatible profiles (v1 profiles)
- Add structured access information that can be reliably queried
- Integrate the [Automatic Access Expiration](AutomaticAccessExpiration.md) to the access information
- Allow for identity information to be transported from social authentication providers to our profile
- Standardize documentation around the profile
- Allow for a standardized API on top of the user profile data ([Person-API](https://github.com/mozilla-iam/person-api))
- Version the profile for possible future updates
- Field-level metadata support
  - Support cryptographic signature per field
  - Support data classification per field
  - Support publisher identifier per field

## Use cases

1. Machines such as TaskCluster want to reliably query Person-API and get authoritative answers about the user's group
   membership. The groups must be easy to query with no ambiguity (i.e. no string-namespacing).
2. User managing GitHub wants to access GitHub user_ids (not email) from logged in users in order to query the GitHub
   API and get relevant data about the user.
3. The access provider wants to expire access when it is no longer used (Automatic Access Expiration).
4. Security team wants to assert that access is lost to certain services (RPs) when they're no longer used by the person
   who used to have access.
5. CIS wants to validate if a publisher has authority over the fields it modified.
6. An RP wants to get profile attributes that are considered public-only, while another, more privileged RP wants to get
   profile attributes that are considered STAFF CONFIDENTIAL.
7. An RP wants to strongly verify that the profile data it's consuming has not been modified anywhere in the IAM
   pipeline and represent what the publisher initially asserted.

## Profile proposal

**Main changes**

1. `_schema` field contains the URL to the json-schema.org validation file. The validation file itself contains the
   revision-equivalent, as well as the environment the schema is written for directly in the URL. This field also
   mirrors it, eg: "person-api.sso.allizom.org" => dev. environment, "v2" is version 2.
2. `emails` structure becomes `identities`. This is a dangerous change as it removes a previously existing field. After
   careful examination we have determined that this field is very unlikely to be currently used and have decided to
   replace it. Identities can contain more than emails, and in particular, can contain an upstream provider's `user_id`.
   Note that a refactor of Person-API and certain CIS libraries is required for this change.
4. `accessInformation` is a new structure that combines `authoritativeGroups` (this structure is known with a very high
   degree of certainty to be unused) and `groups` data. Most sub-fields of that structure are optional, and it's
   organized per "access information publisher". Note also that the metadata here is present in the already-namespaced
   structure.
4. `groups` no longer exists and is re-constructed by identity drivers for compatibility, in particular by the auth0
   driver.
5. All publisher-modifiable fields support metadata, following the
   [AWS-style](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-attribute-metadata.html) metadata for
   JSON documents. The metadata fields may be changed by publishers, however, note that if `user.metadata.authority` is
   changed by a publisher the change will be rejected by CIS and by the validation schema.
6. Add new publisher, "CIS" for information that only CIS is able to provide accurately.
7. In some cases the "Auth0" publisher provides the data even thus it's an intermediary (such as `displayName`,
   `userName` and `primaryEmail`). This is because we otherwise would need a complex multi-publisher-per-field model.
8. Change signature model to be per field instead of per profile, allowing for more flexibility. The signature is
   optional (at least for now) for compatibility.
9. Add `experimental` field which is not to be consumed for important workflows.

### Example profile:

This is all the profile data available to Mozilla IAM, though RPs may be able to see or query only parts of it.

```
{
  "_schema": "https://person-api.sso.mozilla.com/schema/v2/profile",
  "user_id": {
    "metadata": { "authority": "auth0", "signature": "ZOWSLXKxx..", "classification": "PUBLIC" },
    "value": "ad|Mozilla-LDAP-Dev|lmcardle",
  },
  "idp": {
    "metadata": { "authority": "auth0", "signature": "ZOWSLXKxx..", "classification": "WORKGROUP CONFIDENTIAL" },
    "value": "Mozilla-LDAP-Dev"
  },
  "active": {
    "metadata": { "authority": "cis", "signature": "ZOWSLXKxx..", "classification": "WORKGROUP CONFIDENTIAL" },
    "value": true
  },
  "timezone": {
    "metadata": { "authority": "mozilliansorg", "signature": "ZOWSLXKxx..", "classification": "PUBLIC" },
    "value": "Europe/London"
  },
  "lastModified": {
    "metadata": { "authority": "auth0", "signature": "ZOWSLXKxx..", "classification": "PUBLIC" },
    "value": "2017-03-09T21:28:51.851Z"
  },
  "created": {
    "metadata": { "authority": "auth0", "signature": "ZOWSLXKxx..", "classification": "PUBLIC" },
    "value": "2017-03-09T21:28:51.851Z"
  },
  "userName": { 
    "metadata": { "authority": "auth0", "signature": "ZOWSLXKxx..", "classification": "PUBLIC" },
    "value": "lmcardle@mozilla.com"
  },
  "firstName": {
    "metadata": { "authority": "auth0", "signature": "ZOWSLXKxx..", "classification": "PUBLIC" },
    "value": "Leo"
  },
  "lastName": {
    "metadata": { "authority": "auth0", "signature": "ZOWSLXKxx..", "classification": "PUBLIC" },
    "value": "McArdle"
  },
  "preferredLanguage": {
    "metadata": { "authority": "mozilliansorg", "signature": "ZOWSLXKxx..", "classification": "PUBLIC" },
    "value": "en_US"
  },
  "primaryEmail": {
    "metadata": { "authority": "auth0", "signature": "ZOWSLXKxx..", "classification": "PUBLIC" },
    "value": "lmcardle@mozilla.com"
  },
  "identities": {
    "metadata": { "authority": "mozilliansorg", "signature": "ZOWSLXKxx..", "classification": "PUBLIC" },
    "value": [
                {
                  "email": "lmcardle@mozilla.com",
                  "verified": true,
                  "primary": true,
                  "lastModified": "2017-03-09T21:28:51.851Z",
                  "verifier": "MozillaLDAP",
                  "user_id": "dn=mozilla.com,cn=lmcardle"
                },
                {
                  "email": "leomcardle@gmail.com",
                  "verified": true,
                          "primary": false,
                  "verifier": "github-oauth2",
                  "lastModified": "2017-03-09T21:28:51.851Z",
                  "user_id": "834847"
                }
             ]
  },
  "phoneNumbers": {
    "metadata": { "authority": "mozilliansorg", "signature": "ZOWSLXKxx..", "classification": "STAFF CONFIDENTIAL" },
    "value": [ "+4958339847" ]
  },
  "uris": {
    "metadata": { "authority": "mozilliansorg", "signature": "ZOWSLXKxx..", "classification": "STAFF CONFIDENTIAL" },
    "value": [ "https://blog.example.net" ]
  },
  "nicknames": {
    "metadata": { "authority": "mozilliansorg", "signature": "ZOWSLXKxx..", "classification": "PUBLIC" },
    "value": [ "leo" ]
  },
  "SSHFingerprints": {
    "metadata": { "authority": "mozilliansorg", "signature": "ZOWSLXKxx..", "classification": "PUBLIC" },
    "value": [ "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCiAoThvwWQaiTLdkGVvUKbkhmNX9X+cvJZRKnoiv7iGHBKTw4flcTSkwyJQzXTep8R" ]
  },
  "PGPFingerprints": {
    "metadata": { "authority": "mozilliansorg", "signature": "ZOWSLXKxx..", "classification": "PUBLIC" },
    "value": [ "-----BEGIN PGP PUBLIC KEY BLOCK-----\n\nmQINBE94eWwBEADjlvvF8HERvp.....=A0dq\n-----END PGP PUBLIC KEY BLOCK-----\n" ]
  },
  "picture": {
    "metadata": { "authority": "mozilliansorg", "signature": "ZOWSLXKxx..", "classification": "PUBLIC" },
    "value": "https://s.gravatar.com/avatar/ec6e85d15f8411d32f97f5d8a4eab2d3?s=480&r=pg&d=https%3A%2F%2Fcdn.auth0.com%2Favatars%2Flm.png"
  }
  "shirtSize": {
    "metadata": { "authority": "mozilliansorg", "signature": "ZOWSLXKxx..", "classification": "STAFF CONFIDENTIAL" },
    "value": "M"
  },
  "accessInformation": {
    "ldap": {
      "metadata": { "authority": "ldap", "signature": "ZOWSLXKxx..", "classification": "PUBLIC" },
      "value": [
                  {
                    "name": "ldapfoo"
                  },
                  {
                    "name": "vpn_default"
                  }
              ]
    },
    "mozilliansorg": {
      "metadata": { "authority": "mozilliansorg", "signature": "ZOWSLXKxx..", "classification": "PUBLIC" },
      "value": [
                  {
                    "name": "nda"
                  },
                  {
                    "name": "nda"
                  }
               ]
    },
    "hris": {
      "metadata": { "authority": "hris", "signature": "ZOWSLXKxx..", "classification": "STAFF CONFIDENTIAL" },
      "value": [
                  {
                    "name": "costcenter",
                    "value": "1420"
                  },
                  { 
                    "name": "workertype",
                    "value": "employee"
                  },
                  {
                    "name": "egencia",
                    "value": "uk"
                  },
                  {
                    "name": "department",
                    "value": "IT"
                  }
               ]
    },
    "auth0": {
      "metadata": { "authority": "cis", "signature": "ZOWSLXKxx..", "classification": "STAFF CONFIDENTIAL" },
      "value": [
                  {
                    "created": "2010-01-23T04:56:22Z",
                    "lastUsed": "2010-01-23T04:56:22Z",
                    "name": "mozdef1.private.scl3.gmail",
                    "value": "5a5munnfxYjqkaN0su1Kl7USxbqkILQN"
                  }
               ]
    }
  }
  "experimental": {
      "metadata": { "authority": "mozilliansorg", "signature": "ZOWSLXKxx..", "classification": "WORKGROUND CONFIDENTIAL" },
      "value": null
  }
}
```

Schema validator: [here](UserProfilesv2_schema.json)


### Example minimum profile

This is the profile that is sent for RPs that requires authentication and minimum access-control only. This is most of
our RPs. In other words, this is what you can get with the scopes `openid profile` authenticating users.
Note that this profile may be represented as JSON (OpenID Connect), XML (SAML), PersonAPI-like schema, or other format
with slightly different claim or field names for compatibility purposes, though it contains the same contents/data
otherwise. All data is also always sourced from the above profile schema.
Finally, this minimum profile is not available from PersonAPI, as it is already passed through authenticating users.
PersonAPI allows for additional data (scopes/authorization required) or/and different representation of the same
information. It is constructed by our access provider (auth0) by inspecting data provided from the CIS profile v2, which
is itself provided to the access provider by the auth0 identity driver.
This may change in the future, if PersonAPI ever provides an OIDC endpoint.

```
{
  "sub":"ad|Mozilla-LDAP-Dev|lmcardle",
  "email":"lmcardle@mozilla.com",
  "email_verified":true,
  "name":"Leo McArdle",
  "picture":"https://s.gravatar.com/avatar/2a206335017e99ed8b868d931b802f95?s=480&r=pg&d=https%3A%2F%2Fcdn.auth0.com%2Favatars%2Fgd.png",
  "updated_at":"2018-04-11T00:35:36.965Z",
  "https://sso.mozilla.com/claim/groups":["groups here"]
}
```

NOTE: The `https://sso.mozilla.com/claim/groups` claim contains some of `user.accessInformation.*` information. This
does NOT necessarily contain all of the information present in `user.accessInformation` depending on the RP and the
`classification` of the group data.
The access provider makes use of `accessInformation` to allow or deny access (see
https://github.com/mozilla-iam/mozilla-iam/#2-stage-access-validation ), but RPs need to make an authenticated query to
access that data.
