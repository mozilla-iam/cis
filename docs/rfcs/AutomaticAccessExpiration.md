# Automatic Access Expiration

Users may automatically lose access to services when they stop using said service for a certain amount of time.
For example:

- `user A` is granted access to `application A`.
- `application A` has an automatic access expiration setting set to 90 days.
- `user A` does no log in or use `application A` for the next 90 days.

On the 91th day `user A` loses the grant and can no longer login to `application A`. `User A` must request access again.
If `user A` used the application on the 89th day for example, then access would still work for another 90 days:
(89 + 90 = 179 days after first grant)

This is useful for cases where manual group management is tedious, as it ensures users only get access to what they really use.

## User profile and authoritative groups

The [user profile](Profile.md) contains an attribute called `authoritativeGroups`. It contains a list of RP (Relying 
Parties) which utilize the automatic access expiration.
Each time a user logs in to an RP, or that the RP refreshes the session in-flow (i.e. performs an OpenID Connect 
silent authentication), this attribute's timestamp (`lastUsed`) is updated for the user. The timestamp represent the date of last
access for the user.
The CIS validation plugins ensure that only the access provider can modify this attribute.

Simili-JSON representation of this section of the profile:
```
user.authorizedGroups = [
 {
   "created": "2010-01-23T04:56:22Z",
   "lastUsed": "2017-10-01T01:01:01Z",
   "name": "Application A",
   "uuid": "5a5munnfxYjqkaN0su1Kl7USxbqkILQN"
 },
]
```

## Implementation with Auth0 as access provider

### CIS Publisher for Auth0
When Auth0 is the access provider, i.e. the service that provides access (through a SAML assertion or OIDC `id_token` for 
example), we utilize a CIS Publisher plugin in order to update the `user.authorizedGroups` attribute.

The Auth0 CIS Publisher is triggered during calls to Auth0's `/authorize` endpoint (OIDC login) with any parameter, 
including `prompt=none` (in other word for logins and session refreshes).

#### Attributes settings
- `created` is set if the AuthorizedGroup `uuid` did not previously exist and is set to the current time.
- `lastUsed` is set to the current time when the user `/authorize` call occurs. At creation time, this is the same value
as `created`
- `name` is a custom name for this AuthorizedGroup, taken from the `client_name` attribute of the RP in Auth0.
- `uuid` is the `client_id` attribute for the RP in Auth0.

### Auth0 access enforcement
An [Auth0 rule](https://github.com/mozilla-iam/auth0-deploy/blob/master/rules/AccessRules.js) checks the timestamp value during access. If it exceeds a set value (by default, 90 days), 
the access is denied with an error informing the user of what happened, and that the access must be requested again.
