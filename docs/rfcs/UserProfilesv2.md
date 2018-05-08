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


## Possible corresponding API

### Classification scope

**Scopes**: `classification:public`, `classification:staff`, `classification:workgroup`, `classification:individual`

Only returns fields which `metadata.classification` matches the corresponding scope, regardless of ANY other scopes.
Defaults to `classification:public` regardless of the scope selection (i.e. including `classification:public` is
optional for the API caller)

### Publisher Authority scope

**Scopes**: `authority:mozilliansorg`, `authority:auth0`, `authority:hris`, `authority:ldap`

Only authorized for specific publishers. Generally only one type of publisher is allowed one of these scopes (i.e. LDAP
cannot be authorized both `authority:auth0` and `authority:ldap` for example). However, a single publisher may have
multiple, separate pieces of code accessing the API with different tokens and scopes, yet the same `authority` specific
scope (i.e. Mozillians.org may have 3 `client_id` accessing the authorizer with the same `authority:mozilliansorg`
scope).

### Endpoints

All parameters **must** be URL encoded.

- GET,PATCH,PUT,DELETE /v2/{user_id}
- GET,PATCH,PUT,DELETE  /v2/{primaryEmail}

Equivalent endpoints returning raw profile information.

**Scopes**: 
- `read:fullprofile`: supports GET. Entire profile access (minus whatever classification scope is selected)
- `read:profile`: supports GET. Minimal profile access (see below for a minimal profile example)
- `write:fullprofile`: supports PUT. Can post a new, non-existing user profile. Works for all fields.
- `write:profile`: supports PATCH. Can update an existing user profile. Note that this scope does not guarantee success,
  if you fail `signature` verification or `authority` validation. Otherwise works for any field.

Additional, role-specific `write:` and `read:` may be added in the future.

Example minimal profile fields:

- `user_id`
- `primaryEmail`
- `identities.*`
- `firstName`
- `lastName`
- `picture`
- `lastModified`
- `accessInformation.{mozilliansorg.*, ldap.*, hris.*}` Do note again that this does not include fields that are not cleared by
  the classification scope check.

See also the rendered Auth0 OIDC minimal profile further down this document.

- GET,PATCH,PUT /v2/users?q=\*&offset=0&nr=100

Similar to /v2/{user_id} but returns a paginated list of all users. The caller is to repeateadly call the API until all
pages have been fetched, by moving the `offset` value for each query.

**Parameters**:
- `q` query string - allows for searching/filtering results, e.g.: `q="primaryEmail=gdestuynder@mozilla.com"`. Supports
  [filtered expression
syntax](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Query.html#FilteringResults). Default: \*.
- `offset` where the pagination starts. 0 means first page. Default: 0.
- `nr` the number of pages to return. There is one page per user. Default: 100. Maximum value: 1000.
-

**Scopes**:

Same as /v2/{user_id}

**Body**:
The reply includes a super-structure above the user profile structure, as such:

```
{
  "total_pages": 1293, #Amount of pages
  "pages_in_response": 100, # how many pages in this response
  "profiles": [
    {
      .... actual user profile ...
    },
    {
      .... actual user profile ...
    }
    ...
  ]
}
```

- GET /v2/connection/{primaryEmail}

**Scopes**: None required.

Returns valid connection methods for the user.


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
7. In some cases the "Auth0" publisher provides the data even thus it's an intermediary (such as `firstName`,
   `userName` and `primaryEmail`). This is because we otherwise would need a complex multi-publisher-per-field model.
8. Change signature model to be per field instead of per profile, allowing for more flexibility. The signature is
   optional (at least for now) for compatibility.
9. Add `experimental` field which is not to be consumed for important workflows.

### Example profile:

This is all the profile data available to Mozilla IAM, though RPs may be able to see or query only parts of it.

- Schema Schema validator (supports draft 4-7): [here](UserProfilesv2_schema.json)
- Example JSON profile: [here](UserProfilesV2.json)

Example validation:
```
pip install jsonschema
jsonschema -i UserProfilesv2.json UserProfilesv2_schema.json
```

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
  "sub":"ad|Mozilla-LDAP-Dev|lmcardle", #`user_id`
  "email":"lmcardle@mozilla.com",       #`primaryEmail`
  "email_verified":true,                #`identities{'primary':true, 'verified': true}`
  "name":"Leo McArdle",                 #`firstName` + `lastName` which are display names (not necessarily legal names)
  "picture":"https://s.gravatar.com/avatar/2a206335017e99ed8b868d931b802f95?s=480&r=pg&d=https%3A%2F%2Fcdn.auth0.com%2Favatars%2Fgd.png",
  "updated_at":"2018-04-11T00:35:36.965Z", #`lastModified`
  "https://sso.mozilla.com/claim/groups":["groups here"] #`accessInformation.*`
}
```


NOTE: The `https://sso.mozilla.com/claim/groups` claim contains some of `user.accessInformation.*` information. This
does NOT necessarily contain all of the information present in `user.accessInformation` depending on the RP and the
`classification` of the group data.
The access provider makes use of `accessInformation` to allow or deny access (see
https://github.com/mozilla-iam/mozilla-iam/#2-stage-access-validation ), but RPs need to make an authenticated query to
access that data.
