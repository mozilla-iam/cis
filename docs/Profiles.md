# Profiles

User profiles are represented as JSON objects that follow a [JSON
schema](http://json-schema.org/).  The schema contains descriptions of its
fields and is the primary reference for the content of a profile.  It is
available at
[cis/plugins/validation/schema.json](/cis/plugins/validation/schema.json).

A [sample test profile](/tests/data/profile-good.json) is also available,
although it omits many optional fields.

Auth0 provides [additional documented
structure](https://auth0.com/docs/user-profile/normalized) for its profiles. Of
course, using this additional profile information will make the solution
specific to Auth0.

## Schema Validation

Profiles are validated to comply with the
[schema](/cis/plugins/validation/schema.json) on creation and modification.
RP's should not perform additional validation, as the schema may change in a
backward-compatible fashion such as adding additional properties.

## Groups

The profile contains both `groups` and `authoritativeGroups`. The difference is
subtle and it can be difficult to determine what an RP (relying party) should
use for purposes such as access control.

Access providers are expected to maintain and enforce `authoritativeGroups`.
This means it may use information in `authoritativeGroups` to prevent a user to
login to an RP, without relying on the RP to check for access. While all RPs
have an associated `authoritativeGroups` attribute, not all of the RPs access
is prevented by Auth0. Basically for any RP set to "allow anyone in" the access
provider does not prevent access, it just updates attributes; otherwise, it
does/will.

RPs may use `authoritativeGroups` values if they wish, though the access
provider already did the access validation on their behalf

RPs should use groups (any, or combination of groups, as the RP sees fit) with
full knowledge that the groups are only as reliable as the people managing
them. For example, if there is a group called
`mozilliansorg_pplwholikechocolate` that is a directory of chocolate fans
maintained by a fellow Mozillian, it's only as reliable as what this person
decides the members are.  Even LDAP groups can be managed with varying levels
of care. An RP should take that level of care into account when deciding what
level of trust to place in group membership.

## `/userinfo` responses

Note that a profile from an OIDC provider's `/userinfo` endpoint may contain
additional fields specific to that provider. RP's should not use these fields,
preferring the fields described in the schema.
