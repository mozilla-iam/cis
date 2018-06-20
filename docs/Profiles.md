# Profiles

## History

This is what we call the version 2 of the profile. We historically had a lightweight profile that inherited from Auth0
profiles (before OIDC-Conformance was added to Auth0) and SCIM profiles.
Profile version 2 aims to be more flexible, standardized, and support all our major use-cases. We expect this profile to
live a long time before it needs to be updated to a new version.

## Summary

User profiles are represented as JSON objects that follow a [JSON schema](http://json-schema.org/). The schema contains
descriptions of its fields and is the primary reference for the content of a profile. It is available at
<https://person-api.sso.mozilla.com/schema/v2/profile>.

A [sample test profile](/tests/data/profile-good.json) is also available.


## Schema Validation

Profiles are validated to comply with the [schema](https://person-api.sso.mozilla.com/schema/v2/profile) on creation and modification.
Relying parties (RP) may perform additional validation.

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

# Auth0 specific notes

Auth0 provides [additional documented structure](https://auth0.com/docs/user-profile/normalized) for its profiles. Of
course, using this additional profile information will make the solution specific to Auth0 and are only relevant if the
user profile is collected outside of CIS.

Certain RP may be using the Auth0 management API to fetch user data. This method is deprecated in favor of
[PersonAPI](https://github.com/mozilla-iam/person-api), which is an API interface to CIS.
