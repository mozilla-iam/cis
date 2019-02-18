# CIS - Change Integration Service
[![Build Status](https://travis-ci.org/mozilla-iam/cis.svg?branch=master)](https://travis-ci.org/mozilla-iam/cis)
CIS is the Mozilla IAM Change Integration Service.

## Build & Deploy (manual)

Available environment/stages are: `development`, `testing`, `production` (see below for more information)
```
$ make build STAGE=development
$ make release STAGE=development
```

Note that the build & release process happens automatically on the GitHub repository. The above steps are for manual
deploys.

## Test all python modules

This will take care of starting dynalite and other tools, then run tests in tox and clean itself up.
If you get issues with node packages missing simply install them with `npm install <package>` prior to running this.

```
$ cd python-modules
$ make test-tox
```

Each module can also be individually tested:
```
$ cd python-modules/cis_profile
$ make test-tox
```

Other good-to-know testing options:
```
$ cd python-modules/cis_profile
$ tox -r # recreates the Python environment
$ tox -- ./tests/test_profile.py # runs a single test file instead of all tests
```

The tox test environment is stored in `python-modules/.cis-env` by default

## Test endpoints end-to-end

```
$ cd e2e
$ make test-tox
```

## Documentation & Resources

## Where is what?

- e2e contains the end to end tests for CIS
- python-modules contains several libraries which can be called on their own. Many are inter-dependent.
- serverless-functions are serverless.com lambda functions which load some of the python-modules into lambda
- well-known-endpoint contains the Mozilla IAM Well Known endpoint data and it's deployment methods (this endpoint can
  only be manually deployed)
- buildspec.yml contains the AWS Codebuild CD scripts
- .travis.yml contains the travis CI scripts

## Docs

- [CIS Security](docs/Security.md)
- [User Profiles](docs/Profiles.md)

## Draft-RFCs & Proposals (informational-only)
- [RFCs](docs/rfcs/)

## Environments
### Production (prod)

This is what you expect. Tagged releases (SemVer, e.g. 1.2.3) from this repository are what run in production.
It uses a specific set of signing and verifications keys.

URLs:
- https://change.api.sso.mozilla.com
- https://person.api.sso.mozilla.com
- https://auth.mozilla.com/.well-known/mozilla-iam (contains all necessary information, URLs, audience, keys, etc.)

Audience:
- api.sso.mozilla.com

### Testing (testing)

This is what is usually called staging. It contains code and data similar to production and is used to ensure that the production deployment will work.
It uses the same set of keys as production.

Tagged releases (SemVer pre-releases, e.g. 1.2.3-pre) from this repository are what run in testing.

URLs:
- https://change.api.test.sso.allizom.org
- https://person.api.test.sso.allizom.org
- https://auth.allizom.org/.well-known/mozilla-iam (contains all necessary information, URLs, audience, keys, etc.)

Audience:
- api.test.sso.allizom.org

### Development (dev)

This is for local testing and development. This is also what is in the `master` branch of this repository.
It uses a development set of keys for signing and verification.

URLs:
- https://change.api.dev.sso.allizom.org
- https://person.api.dev.sso.allizom.org
- https://auth.allizom.org/.well-known/mozilla-iam (contains all necessary information, URLs, audience, keys, etc.)

Audience:
- api.dev.sso.allizom.org
