# CIS - Change Integration Service
[![Build Status](https://travis-ci.org/mozilla-iam/cis.svg?branch=master)](https://travis-ci.org/mozilla-iam/cis)

# THIS IS A WIP BRANCH FOR PROFILE v2

This is a work in progress for updating docs and design concepts for profile v2.  Things may not all be updated as yet.

## Documentation & Resources

- [CIS Security](docs/Security.md)
- [User Profiles](docs/Profiles.md)

## Draft-RFCs & Proposals (informational-only)
- [RFCs](docs/rfcs/)

## Summary

CIS is the Mozilla IAM Change Integration Service.

TODO: Better summary :)

## Environments
### Production (prod)

This is what you expect. Tagged releases (SemVer, e.g. 1.2.3) from this repository are what run in production.
It uses a specific set of signing and verifications keys.

URLs:
- https://change.api.sso.mozilla.com
- https://person.api.sso.mozilla.com
- https://auth.mozilla.com/.well-known/mozilla-iam

Audience:
- api.sso.mozilla.com

### Testing (testing)

This is what is usually called staging. It contains code and data similar to production and is used to ensure that the production deployment will work.
It uses the same set of keys as production.

Tagged releases (SemVer pre-releases, e.g. 1.2.3-pre) from this repository are what run in testing.

URLs:
- https://change.api.test.sso.allizom.org
- https://person.api.test.sso.allizom.org
- https://auth.allizom.org/.well-known/mozilla-iam

Audience:
- api.test.sso.allizom.org

### Development (dev)

This is for local testing and development. This is also what is in the `master` branch of this repository.
It uses a development set of keys for signing and verification.

URLs:
- https://change.api.dev.sso.allizom.org
- https://person.api.dev.sso.allizom.org
- https://auth.allizom.org/.well-known/mozilla-iam

Audience:
- api.dev.sso.allizom.org
