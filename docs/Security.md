# Security
## Threat model
### Integrity

1. Attacker able to modify CIS code or data/identity vault/stream (by owning
   serverless functions or the IAM account)
    1. Identities must be verifiable without trusting CIS
    2. Identity's authentication data is not stored by CIS

2. Attacker able to modify publisher (f.e. "mozillians.org") user profiles
    1. CIS must validate all changes so that a publisher may only emit changes that
       pertain to it's area of authority
    2. Identity must be verified out-of-band (2FA, OIDC OP verified)
    3. Identity's authorizations (groups membership) may-be additionally verified
       through Mozilla's "2nd opinion" which is also out of band

3. Attacker able to modify identity drivers
    1. Identity must be verified out-of-band (2FA, OIDC OP verified)
    2. Identity's authorizations (groups membership) may-be additionally verified
       through Mozilla's "2nd opinion" which is also out of band

## Availability

4. Attacker brings CIS down or delete the identity vault
    1. CIS is not relied upon by identity providers (OIDC OP such as Auth0, LDAP,
       etc.) as they cache the data on their own
    2. CIS identity vault may be lost and re-created from identity provider's data
    3. User identity contains certain groups that allow for an expiration
       attribute, so that access may be lost without any additional CIS information
    4. User identity may be invalidated/blocked outside of CIS

## Confidentiality

5. Attacker grabs the identity vault
    1. No credentials are stored on CIS
    2. Attacker may get sensitive group information
    3. Attacker may get personal data such as t-shirt size or email addresses

## Resulting security requirements

- (1) CIS requires all events to be signed by each stream publisher (each
  publisher own a private, unique key that is trusted by CIS).
- (1) Identity events are submitted with the entire identity (no partial
  changes, the full copy of the identity is always transmitted) As identities
are sent in their entirety with a signature, it is possible to relying parties
can verify signatures, i.e. changes are verifiable end-to-end)
- (2) Each stream publisher belongs to a validation plugin which verifies only
  allowed identity fields have been modified.
  - A publisher generally can modify it's own user groups (but not other
    publisher's)
  - Certain publisher can modify different fields, such as t-shirt size, name,
    etc.
- (3) User identity never contains any authentication tokens. These are stored
  by identity providers.
- (4) Support the use of `AuthoritativeGroups` per relying party automatically
  with default-expiration.
- (5) KMS key is required to access data
