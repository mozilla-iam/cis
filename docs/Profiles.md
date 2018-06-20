# Profiles

## History

This is what we call the version 2 of the profile. We historically had a lightweight profile that inherited from Auth0
profiles (before OIDC-Conformance was added to Auth0) and SCIM profiles.
Profile version 2 aims to be more flexible, standardized, and support all our major use-cases. We expect this profile to
live a long time before it needs to be updated to a new version.

## Summary

User profiles are represented as JSON objects that follow a [JSON schema](http://json-schema.org/). The schema contains
descriptions of its fields and is the primary reference for the content of a profile.

- The **Core profile** schema is available at <https://person-api.sso.mozilla.com/schema/v2/profile/core>.
- The **Extended profile** schema is available at <https://person-api.sso.mozilla.com/schema/v2/profile/extended>.

### Core vs Extended profiles principles

- Do not duplicate data between "Core profile data" and "Extended profile data"
- "Core profile data" is profile data than *any* RP needs to function with IAM
- The "Extended profile data" may contain additional claims over time
- Access to "Extended profile data" fields may require specific approval for privacy reasons
- Fields are using `this_format` (all lower-case, `_` as word separator)
- All "Extended profile data" fields are **optional**
- Top level fields use the standard attribute structure (see below) unless otherwise noted

### Core Profile

Top level fields for the Core profile.

```
schema: https://person-api.sso.mozilla.com/schema/v2/profile/core
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
tags: list of tags the user associates with. formerly called mozillians groups
pronouns: prefered user pronouns
employe_id: user's Staff id
business_title: user's official Staff title
manager: user's official Staff manager
office_location: user's preferred Mozilla office location
desk_number: user's official office desk number, if any
picture: link to a user picture
uris: list of uris (urls) that the user associate with, such as their website
phone_numbers: telephone numbers for the user
timezone: user's preferred timezone
preferred_languages: user's preferred languages to write or speak
```

### Standard attribute structure

This is the schema that every attribute in the profile **should** follow. Where noted, certain top level attributes may
present a custom list or array which contain the standard attribute structure as their ultimate child(s).

The top-level attribute represents the attribute name.

The *signature* field is used to certify the attribute has been verified by a publisher, and potentially additional
sources such as users (humans). This allows for performing out-of-band signatures and verifications that the IAM systems
cannot interfer with. No automated IAM system may hold the private signing keys for `additional` signatures.

The *metadata* field contains additional information about the attribute, which allows the IAM systems to understand
whom may have access to this attribute for example.

The *values* field is always a list containing attribute values. It may contain only one single value.

```
dummy_attribute: {
  "signature": {
    "publisher": { "alg": "HS256", "typ": "jwt", "value": "dummy signature" },
    "additional": [
      { "alg": "RSA", "typ": "PGP", "value": "dummy user pgp signature" }
    ]
  },
  "metadata": {
    "classification": "PUBLIC",
    "last_modified": "2018-01-01T00:00:00",
    "created": "2018-01-01T00:00:00",
    "publisher_authority": "dummy publisher identifier"
  },
  "values": [
    "dummy attribute value",
    "another dummy attribute value"
  ],
}
```

## Schema Validation

Profiles are validated to comply with the [schemas](https://person-api.sso.mozilla.com/schema/v2/profile/core) on
creation and modification. Relying parties (RP) may perform additional validation at their discretion.

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
