# CIS - Change Integration Service
[![Build Status](https://github.com/mozilla-iam/cis/actions/workflows/make-test.yml/badge.svg)](https://github.com/mozilla-iam/cis/actions/)
CIS is the Mozilla IAM Change Integration Service.

## I'm an API user, where do I start?

See [PersonAPI](docs/PersonAPI.md) docs for querying the API.

## Pre-Requisites 

* Docker
* Docker-Compose
* Make

### Continuous Integration

* GitHub Actions (fork the repository on GitHub to begin)
* Docker Hub API key (access level public-readonly)

## Build & Deploy (manual)

_Note: All development is now driven via docker-compose._

Available environment/stages are: `development`, `testing`, `production` (see below for more information)
```
$ make build STAGE=development
$ make release STAGE=development
```

For all the following commands first run `make developer-shell`.  This starts a docker-container with all the dependencies as well as shared volumes with the source.

Or you can deploy a single function as such, instead of running `make release` (note that you may still want to run
`make build` which both builds and upload the Lambda layers:
```
$ make -C serverless deploy-ldap-publisher
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
# How changes are published to CIS

![Publisher](/docs/images/publisher_flow.png?raw=true "Publisher Diagram")


## Additional Documentation & Resources

## Where is what?

- e2e contains the end to end tests for CIS. These are a good source of examples on how to use the CIS API.
- python-modules contains several libraries which can be called on their own. Many are inter-dependent.
- serverless-functions are serverless.com lambda functions which load some of the python-modules into AWS Lambda.
- well-known-endpoint contains the Mozilla IAM Well Known endpoint data and it's deployment methods (this endpoint can
  only be manually deployed)
- buildspec.yml contains the AWS Codebuild CD scripts.
- .github/workflows/make-test.yml contains the GitHub Actions CI script.

Note that many directories contain their own README.md, which has more detailed information.

## Docs

These are the general docs for the concepts behind CIS.

- [CIS Security](docs/Security.md)
- [User Profiles](docs/Profiles.md)
- [AuthenticatorAssuranceIndicator](docs/AuthenticatorAssuranceIndicator.md)
- [AccessFile apps.yml](docs/AccessFile.md)
- [Well-known endpoint](docs/Well-known%20Endpoint.md)
- [Webhook Notifications](docs/Hooks.md)

## Draft-RFCs & Proposals (informational-only)
- [RFCs](docs/rfcs/)

## Environments
### Production (prod)

This is what you expect. Tagged releases (SemVer, e.g. 1.2.3) from this repository are what run in production.
It uses a specific set of signing and verifications keys.
This is the environment you will get access to if you request API access to CIS. This is also the environment that DinoPark and DinoPark Beta access.

URLs:
- https://change.api.sso.mozilla.com
- https://person.api.sso.mozilla.com
- https://auth.mozilla.com/.well-known/mozilla-iam (contains all necessary information, URLs, audience, keys, etc.)

Audience:
- api.sso.mozilla.com

### Testing (testing)

This is what is usually called staging. It contains code and data similar to production and is used to ensure that the production deployment will work.
It uses the same set of keys as production. This environment contains real data and is **not** guaranteed to persistent. In practice this means the data is reset periodically. This environment is meant for general QA.

Tagged releases (SemVer pre-releases, e.g. 1.2.3-pre) from this repository are what run in testing.

URLs:
- https://change.api.test.sso.allizom.org
- https://person.api.test.sso.allizom.org
- https://auth.allizom.org/.well-known/mozilla-iam (contains all necessary information, URLs, audience, keys, etc.)

Audience:
- api.test.sso.allizom.org

### Development (dev)

This is for local testing and development. This is also what is in the `master` branch of this repository.
It uses a development set of keys for signing and verification. This environment contains fake data and is neither persistent neither guaranteed to be stable, though it should be almost always functional.
Access to this environment may be granted temporarily to diagnose specific issues, features, etc. as they're being developed, but is not meant for general QA.

URLs:
- https://change.api.dev.sso.allizom.org
- https://person.api.dev.sso.allizom.org
- https://auth.allizom.org/.well-known/mozilla-iam (contains all necessary information, URLs, audience, keys, etc.)

Audience:
- api.dev.sso.allizom.org
