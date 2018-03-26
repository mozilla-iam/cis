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

```
{
  "_schema": "https://person-api.sso.mozilla.com/profile/v2/schema",
  "user_id": "ad|Mozilla-LDAP-Dev|lmcardle",
  "timezone": "Europe/London",
  "active": true,
  "lastModified": "2017-03-09T21:28:51.851Z",
  "created": "2017-03-09T21:28:51.851Z",
  "userName": "lmcardle@mozilla.com",
  "displayName": "Leo McArdle",
  "firstName": "Leo",
  "lastName": "McArdle",
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
