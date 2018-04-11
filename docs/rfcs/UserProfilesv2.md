# User Profiles (v2)

This document describes the Mozilla IAM user profiles version 2.

IAM Goals:
- MUST stay compatible with v1 (current profiles)
- Add structured access information that can be reliably queried
- Integrate the [Automatic Access Expiration](AutomaticAccessExpiration.md) to the access information
- Allow for identity information to be transported from social authentication providers to our profile
- Standardize documentation around the profile
- Allow for a standardized API on top of the user profile data ([Person-API](https://github.com/mozilla-iam/person-api))
- Version the profile for possible future updates

## Use cases

1. Machines such as TaskCluster want to reliably query Person-API and get authoritative answers about the user's group
   membership. The groups must be easy to query with no ambiguity (i.e. no string-namespacing).
2. User managing GitHub wants to access GitHub user_ids (not email) from logged in users in order to query the GitHub
   API and get relevant data about the user.
3. The access provider wants to expire access when it is no longer used (Automatic Access Expiration).
4. Security team wants to assert that access is lost to certain services (RPs) when they're no longer used by the person
   who used to have access.

## Profile proposal

**Main changes**

1. `_schema` field contains the URL to the json-schema.org validation file. The validation file itself contains the
   revision-equivalent, as well as the environment the schema is written for directly in the URL. This field also
   mirrors it, eg: "person-api.sso.allizom.org" => dev. environment, "v2" is version 2.
2. `emails` structure becomes `identities`. This is a dangerous change as it removes a previously existing field. After
   careful examination we have determined that this field is very unlikely to be currently used and have decided to
   replace it. Identities can contain more than emails, and in particular, can contain an upstream provider's `user_id`.
   Note that a refactor of Person-API and certain CIS libraries is required for this change.
3. `groups` are unchanged for compatibility.
4. `accessInformation` is a new structure that combines `authoritativeGroups` (this structure is known with a very high
   degree of certainty to be unused) and `groups` data. Most sub-fields of that structure are optional, and it's
   organized per "access information publisher".

### Example profile:

This is all the profile data available to Mozilla IAM, though RPs may be able to see or query only parts of it.

```
{
  "_schema": "https://person-api.sso.mozilla.com/schema/v2/profile",
  "user_id": "ad|Mozilla-LDAP-Dev|lmcardle",
  "timezone": "Europe/London",
  "active": true,
  "lastModified": "2017-03-09T21:28:51.851Z",
  "created": "2017-03-09T21:28:51.851Z",
  "userName": "lmcardle@mozilla.com",
  "displayName": "Leo McArdle",
  "preferredLanguage": "en_US",
  "primaryEmail": "lmcardle@mozilla.com",
  "identities": [
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
  ],
  "phoneNumbers": [
    "+4958339847"
  ],
  "uris": [
    "https://blog.example.net"
  ],
  "nicknames": [
    "leo"
  ],
  "SSHFingerprints": [
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCiAoThvwWQaiTLdkGVvUKbkhmNX9X+cvJZRKnoiv7iGHBKTw4flcTSkwyJQzXTep8R"
  ],
  "PGPFingerprints": [
    "-----BEGIN PGP PUBLIC KEY BLOCK-----\n\nmQINBE94eWwBEADjlvvF8HERvp.....=A0dq\n-----END PGP PUBLIC KEY BLOCK-----\n"
  ],
  "picture": "https://s.gravatar.com/avatar/ec6e85d15f8411d32f97f5d8a4eab2d3?s=480&r=pg&d=https%3A%2F%2Fcdn.auth0.com%2Favatars%2Flm.png",
  "shirtSize": "M",
  "groups": [
    "0A_legacy_structure_only_please_use_accessInformation_instead",
    "mozilliansorg_bar",
    "mozilliansorg_foo",
    "hris_foo",
    "ldapfoo"
  ],
  "accessInformation": {
    "ldap": [
      {
        "name": "ldapfoo"
      },
      {
        "name": "vpn_default"
      }
      ],
    "mozilliansorg": [
      {
        "name": "nda"
      },
      {
        "name": "nda"
      }
      ],
    "hris": [
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
      ],
    "accessprovider": [
      {
        "created": "2010-01-23T04:56:22Z",
        "lastUsed": "2010-01-23T04:56:22Z",
        "name": "mozdef1.private.scl3.gmail",
        "value": "5a5munnfxYjqkaN0su1Kl7USxbqkILQN"
      }
    ]
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
information. 
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

NOTE: The `https://sso.mozilla.com/claim/groups` claim contains `user.groups` information. This does NOT contain all of
the information present in `user.accessInformation`, for example, it does NOT contain HRIS manager name, or access
provider data. It DOES contain all LDAP groups and all Mozillians.org **access** groups (such as `mozilliansorg_nda`)
The access provider makes use of `accessInformation` to allow or deny access (see
https://github.com/mozilla-iam/mozilla-iam/#2-stage-access-validation ), but RPs need to make an authenticated query to
access that data.
