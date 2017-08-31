# Profiles

User profiles are represented as JSON objects that follow a [JSON schema](http://json-schema.org/). The schema contains
descriptions of its fields and is the primary reference for the content of a profile. It is available at
[cis/plugins/validation/schema.json](/cis/plugins/validation/schema.json).

A [sample test profile](/tests/data/profile-good.json) is also available.


## Schema Validation

Profiles are validated to comply with the [schema](/cis/plugins/validation/schema.json) on creation and modification.
RP's should not perform additional validation, as the schema may change in a backward-compatible fashion such as adding
additional properties.

## Groups

The profile contains both `groups` and `authoritativeGroups` attributes. The differences and handling of these groups 
is important.

### The `groups` attribute

RPs should use the `groups` attribute (any, or combination of groups, as the RP sees fit) with full knowledge that the
groups are only as reliable as the people managing them.  For example, if there is a group called
`mozilliansorg_pplwholikechocolate` that is a directory of chocolate fans maintained by a fellow Mozillian, it's only as
reliable as what this person decides the members are.  Even LDAP groups can be managed with varying levels of care. An
RP should take that level of care into consideration when deciding what level of trust to place in group membership.

Additionally, `groups` are prefixed as follows:
- `mozilliansorg_`: these groups are provided by the Mozillians.org CIS Publisher.
- `workday_`: these groups are provided by the WorkDay CIS Publisher.

Other prefixes following this naming scheme, such as `team_` are regular LDAP groups. This also includes non-prefixed
groups.

**NOTE**: The structure and prefixes of the `group` attribute have been selected amonsgt various solutions in order to
 provide forward and backward compatibility for all RP's and Publishers.

### The `authoritativeGroups` attribute

The access provider (such as Auth0) is expected to maintain and enforce `authoritativeGroups`. It is updated
through a CIS publisher.

Each group in `authoritativeGroups` has a one to one mapping with an RP. This mapping is recorded in the
`authoritativeGroups.uuid` field.
The `authoritativeGroups.lastUsed` field is updated by the access provider whenever this group has last granted access 
for a user.

RPs may use `authoritativeGroups` values if they wish, though the access provider already did access validation on
their behalf.

### Access provider control decisions

The access provider use `authoritativeGroups` to enforce access decisions (i.e. preventing login to an RP) if these
conditions are met:

- User access expiration is enabled for this RP, and the `authoritativeGroups.lastUsed` attribute is older than the
  expiration date.
- Specific rules or groups are whitelisted for this RP and the access provider was configured to enforce access on
  behalf of the RP. This is useful for blanket access statements such as "only Staff employees can access the PTO
application".


## `/userinfo` endpoint and `id_token` responses

User profiles from an OIDC provider's `/userinfo` endpoint may contain additional fields specific to that
provider. RP's should generally not use these fields, preferring the fields described in the schema as the additional
OIDC fields may be access provider specific.

## Profile updates

User profiles are updated by CIS Publisher by fetching the latest version of a user profile, performing modifications to
it, and submitting the new version in it's entierety to CIS. This means the publisher is responsible for integrating
attributes, and CIS will check and validate that the integration has been performed correctly, then will either accept
or refuse the change as a complete user profile update.

### Attribute validation during profile updates

Attributes are updated by CIS Publishers by sending a specifically formatted [Event](cis/docs/Event.md). CIS possesses 
a validation mechanism that enforces which CIS Publisher is allowed to modify which attributes, and which values inside
the said attributes.

For example, the CIS Publisher `mozilliansorg` may not modify, add, delete `groups` that are not prefixed with
`mozilliansorg_`. It also may not modify the `authoritativeGroups` attribute.
On other other hand, the CIS Publisher Auth0 (access provider) can modify `authoritativeGroups` but not `groups.
This logic is write in code through [validation plugins](cis/plugins/validation).

# Auth0 specific notes

Auth0 provides [additional documented structure](https://auth0.com/docs/user-profile/normalized) for its profiles. Of
course, using this additional profile information will make the solution specific to Auth0 and are only relevant if the
user profile is collected outside of CIS.
