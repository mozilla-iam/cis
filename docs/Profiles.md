# Profiles

## History

This is what we call the version 2 of the profile. We historically had a lightweight profile that inherited from Auth0
profiles (before OIDC-Conformance was added to Auth0) and SCIM profiles.
Profile version 2 aims to be more flexible, standardized, and support all our major use-cases. We expect this profile to
live a long time before it needs to be updated to a new version.

Note that there are few unspecified attribute values, as once they've been presented to a relying party (RP) it is no
longer possible to retire the attribute without potentially breaking the flow for said RP(s).

## Summary

User profiles are represented as JSON objects that follow a [JSON schema](http://json-schema.org/). The schema contains
descriptions of its fields and is the primary reference for the content of a profile.

- The **Core+Extended profile** schema is available at <https://person-api.sso.mozilla.com/schema/v2/profile>. It
  will validate profiles that contains data from both Core and Extended profiles in the same document.
- The **Core profile** schema is available at <https://person-api.sso.mozilla.com/schema/v2/profile/core>.
- The **Extended profile** schema is available at <https://person-api.sso.mozilla.com/schema/v2/profile/extended>.

When using these schemas, you *should* attempt to fetch the latest version every time (it's fine to cache it for some
period of time, but the schemas may sometimes be updated).

### Core vs Extended profiles principles

- Do not duplicate data between "Core profile data" and "Extended profile data"
- "Core profile data" is profile data than *any* RP needs to function with IAM
- The "Extended profile data" may contain additional claims over time, and is generally user-supplied data
- Access to "Extended profile data" fields may require specific approval for privacy reasons
- Fields are using `this_format` (all lower-case, `_` as word separator)
- All "Extended profile data" fields are **optional** and may be missing have have `null` values
- Top level fields use the standard attribute structure (see below) unless otherwise noted

### Core Profile

Top level fields for the Core profile.

```
schema: https://person-api.sso.mozilla.com/schema/v2/profile/core (this field does not follow the standard attribute
structure)
user_id: unique_id
login_method: ldap, fxa, ...
active: true
last_modified: date of last change
created: date of profile creation
username: a short username with no spaces
first_name: user's preferred first name
last_name: user's preferred last name
primary_email: user's main email, such as xxx@mozilla.com
identities: list of additional user identities on other IdPs, such as their alternative emails, github accounts, etc.
ssh_public_keys: list of OpenSSH public keys for the user
pgp_public_keys: list of PGP public keys for the user
access_information: structure containing group data and other information used to validate if the user should be granted
access or not. This structure uses a list of standard attributes.
```

### Extended Profile

Top level fields for the Extended profile. Fields that are staff-only are not used for non-staff users.

```
fun_title: a title that the user identifies with, not their official Staff title
description: a free form text field for the user to put information about themselves in
location_preference: where the user would like to appear to be located (such as a country, city, etc.)
office_location: user's preferred Mozilla office location
timezone: user's preferred timezone
preferred_languages: user's preferred languages to write or speak
tags: list of tags the user associates with. formerly called mozillians groups
pronouns: prefered user pronouns
picture: link to a user picture
uris: list of uris (urls) that the user associate with, such as their website
phone_numbers: telephone numbers for the user
alternate_name: name in local language for spelling or display purposes in case the user prefer communicating their name in a
different way to international users, or any other alternative name
```

### Standard attribute structure

This is the schema that every attribute in the profile **should** follow. Where noted, certain top level attributes may
present a custom list or associative array which contain the standard attribute structure as their ultimate child(s).

The top-level attribute represents the attribute name.

**Rules** to follow when modifying this structure are outlined below:

#### Signature field

The *signature* field is used to certify the attribute has been verified by a publisher, and potentially additional
sources such as users (humans). This allows for performing out-of-band signatures and verifications that the IAM systems
cannot interfere with. No automated IAM system may hold the private signing keys for `additional` signatures.

- JWT and PGP are supported, with various algorithms (see schema for allowed algorithms).
- The publisher signature is always required. The publisher identity is stored in `metadata.publisher_authority`.
- The additional signatures may be added by any publisher, and is generally used for user-supplied signatures.
- The data that is signed are the contents of the structure the field `signature` is in, minus the `signature` structure
  itself. E.g. below: `dummy_attribute.*` *minus* `dummy_attribute.signature.*` would be the object to sign.
- The signed object data is serialized by alpha-numerical order (`javascript: JSON.stringify(x)` or `python:
  json.dumps(x, separators=(',',':'))` for example).


#### Metadata field

The *metadata* field contains additional information about the attribute, which allows the IAM systems to understand
whom may have access to this attribute for example.
- We follow the [Mozilla Data Classification](https://wiki.mozilla.org/Security/Data_Classification) standard for the
  *classification* field.
- The `publisher_authority` is the same publisher identifier as used for the signature fields.
- The `verified` field is set by the `publisher_authority` and represent the fact that **all** values in this object
  have been strongly verified to be correct. For example, an email has been verified to belong to the owner by sending
them an email with a link to verify that they own it. If *any* value is unverified, then the whole object shows as
`verified: false`.

**value** and **values** fields are exclusionary, only one of them may be used.
If used, the *value* field may be of any type: string, boolean, integer, list or associative array value.
If used, the *values* field is of type associative array and may contain any sub-value.

```
"dummy_attribute": {
  "signature": {
    "publisher": { "alg": "HS256", "typ": "jwt", "value": "dummy signature" },
    "additional": [
      { "alg": "RSA", "typ": "PGP", "value": "dummy user pgp signature" }
    ]
  },
  "metadata": {
    "classification": "PUBLIC",
    "last_modified": "2018-01-01T00:00:00Z",
    "created": "2018-01-01T00:00:00Z",
    "publisher_authority": "dummy publisher identifier"
  },
  "values": {
    "title": "dummy attribute value",
    "other_title": "another dummy attribute value"
  }
}
```

## Schema Validation

Profiles are validated to comply with the [schemas](https://person-api.sso.mozilla.com/schema/v2/profile) on
creation and modification. Relying parties (RP) may perform additional validation at their discretion.

Note that you may manually run validation for test profiles by using the Makefile under `profile_data`:
`make validate-core-plus-extended-test-profile` for example.

## `/userinfo` endpoint and `id_token` responses

User profiles from an OIDC provider's `/userinfo` endpoint may contain additional fields specific to that
provider. RP's should generally not use these fields other than the [OIDC Standard
claims](https://openid.net/specs/openid-connect-core-1_0.html#StandardClaims), preferring the fields described in the
schema as the additional OIDC fields may be access provider specific.

## Profile updates

User profiles are updated by CIS Publishers such as LDAP, HRIS and Mozillians.org by fetching the latest version of a
user profile, performing modifications to fields they are marked as publisher for, and submitting the new version to
CIS.

CIS will revalidate all changes and verify changes have been signed before integrating them in the user profile database
(ID Vault).

### Attribute validation during profile updates

Attributes are updated by CIS Publishers by sending a specifically formatted [Event](cis/docs/Event.md). CIS possesses 
a validation mechanism that enforces which CIS Publisher is allowed to modify which attributes, and which values inside
the said attributes.

This logic is written in code at [validation plugins](cis/plugins/validation).

# Appendix

## Auth0 specific notes

Auth0 provides [additional documented structure](https://auth0.com/docs/user-profile/normalized) for its profiles. Of
course, using this additional profile information will make the solution specific to Auth0 and are only relevant if the
user profile is collected outside of CIS.

Certain RP may be using the Auth0 management API to fetch user data. This method is deprecated in favor of
[PersonAPI](https://github.com/mozilla-iam/person-api), which is an API interface to CIS.

## Schema generation notes

Schemas are generated by creating a complete (i.e. "all fields") sample user profile, and using the schema generator at
<https://app.quicktype.io/#l=schema>. The resulting schema is then hand-modified and follows the JSON Schema standard.

Finally, the schema syntax is verified, for example at <https://jsonschemalint.com/#/version/draft-06/markup/json> and
normally verified to be compatible with draft-04 at the minimum (this is because most libraries currently support this
draft, even thus newer versions are available).

A YAML-equivalent profile may be generated and verified, for example at <https://json-schema-everywhere.github.io/yaml>

## Profile samples

Note that profiles may be written in YAML instead of JSON, albeit **all** processing will be performed in JSON. This
means all profiles must be converted to JSON before being submitted or used.

- [Core profile (JSON)](profile_data/user_profile_core.json)
- [Core+Extended profile (JSON)](profile_data/user_profile_core_plus_extended.json)
- [Core+Extended profile (YAML, commented)](profile_data/user_profile_core_plus_extended.yml)

## Schema source

Note that you should **not** get the schemas from here for production use, nor may you copy them locally. Instead, use
the official URLs to source the schema from, which are located at the top of this document.

The source schemas here are only provided for testing and informational purposes.

- [Core profile schema](profile_data/profile_core.schema)
- [Extended profile schema](profile_data/profile_extended.schema)
- [Core plus extended profile schema](profile_data/profile.schema)
