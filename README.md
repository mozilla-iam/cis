# CIS - Change Integration Service
[![Build Status](https://github.com/mozilla-iam/cis/actions/workflows/make-test.yml/badge.svg)](https://github.com/mozilla-iam/cis/actions/)
CIS is the Mozilla IAM Change Integration Service.

The Change Integration Service is a service responsible for aggregating all
information about our employees and contributors. This includes data such as:

* Access information (from LDAP and the People Directory);
* Identities (GitHub, LDAP);
* Employment-related info (cost centre, manager, etc).

This information is used throught various systems and provide a way for info to
propagate throughout the system.

An example:

1. A user is added to a new group on the People Directory;
2. The People Directory fires a webhook to CIS (this repository);
3. CIS's Change Service updates the user;
4. A webhook is fired afterwards, which calls out to
5. Auth0, which updates the user.

This repository is laid out in the following way:

- e2e contains the end to end tests for CIS. These are a good source of
  examples on how to use the CIS API.
- `python-modules` contains several libraries which can be called on their own.
  Many are inter-dependent.
- `serverless-functions` are serverless.com lambda functions which load some of
  the python-modules into AWS Lambda.
- `well-known-endpoint` contains the Mozilla IAM Well Known endpoint data and
  it's deployment methods (this endpoint can only be manually deployed)
- `buildspec.yml` contains the AWS Codebuild CD scripts.
- `.github/workflows/make-test.yml` contains the GitHub Actions CI script.

Note that many directories contain their own README.md, which has more detailed
information.

## I'm an API user, where do I start?

See [PersonAPI](docs/PersonAPI.md) docs for querying the API.

## Prerequisites

* Docker
* Python 3.9

### Some notes on Mac

You'll need the following installed via `brew`:

```
brew install -f openssl@1.1
brew install libpq
```

There are additional variables you may need in your environment, see
`dev/mise-mac-helper.sh` for more information.

## Optional prerequisites

* [mise] -- this makes your life a lot easier, setting up a virtual environment,
  etc, etc.

[mise]: https://mise.jdx.dev/

### Developing locally

*nb.* `libpq` and `openssl` (v1) will need to be installed, and the various
compiler flags (`LDFLAGS` and `CPPFLAGS`) will need to be amended.

```
pip install -r requirements/core.txt -r requirements/test.txt
pip install -e python-modules/cis_*
```

### Continuous Integration

For every commit and pull request we'll run our test suite.

Locally, this can be done by running:

```
./ci/test.sh
```

## Build

We use various environment variables to decide which "environment/stage" to
deploy to. By default, when building locally we'll use the `development-dirty`
stage. Available environment/stages are: `development`, `testing`,
`production`.

The CI pipeline will build and upload a new Lambda Layer for you.

* `development`: publishes a new layer when `master` is updated;
* `testing`: publishes a new layer when a _pre-release_ is published;
* `production`: publishes a new layer when a *release* is published.

To build and upload a new Lambda layer, run:

```
./ci/layer-build.sh
./ci/layer-upload.sh
```

*nb.* You'll need AWS credentials.

### A brief digression into ci/layer-build.sh

Instead of depending on the environment of a CI runner, your Mac, or an some
other ad-hoc one, we build a Docker image and copy files out of it.

You're able to control the Python runtime version (defaults to `3.9.23`,
controlled by `TARGET_PYTHON_VERSION`), as well as the target architecture
(defaults to `x86_64`, controlled by `TARGET_ARCH`).

By using Docker we're able to gloss over:

* the different ways dependencies are installed (primarily GitHub's runner and
  your laptop) (we use Python's `slim-bookworm`, and thus use `apt`);
* the host architecture (via `--platform linux/$TARGET_ARCH`); and
* weird ways Python may be set up (we install into the `build` user's `$HOME` directory).

The general process is:

1. Build a Docker image with:
  1. install all dependencies (system: libffi, runtime: `requirements/*.txt`);
  2. install all Python modules (`python-modules/cis_*`).
2. Run the Docker image.
3. Copy files out of that image.
3. Zip the contents up from the build environment.

We're specific when it comes to the Python version and architecture because the
layout of the `site-packages` directory ends up being different across Python
versions and the libraries we link with are architecture-specific.

This allows us some agility when it comes to different Python versions and
architectures, which we'll need since it seems like Lambda autoupgrades some of
our runtimes for us (breaking itself in the process).

### A brief digression into ci/layer-upload.sh

When the Lambdas are deployed via `serverless`, they read a parameter from AWS
Systems Manager.

The GitHub pipeline assumes the `GitHubCIS` role (defined in
`terraform/build/github_builder_role.tf`), which has enough permissions to:

1. Publish a new Lambda Layer version;
2. Update _the new_ parameter.

Publishing a layer from your laptop and then using it is intentionally a pain,
but possible.

To use a custom layer, say the `development-dirty` one, you'll need to change
the `functions.<function>.layers` array in the various `serverless.yml` files
(followed by a `serverless deploy`).

To publish a new `development-dirty` layer, run:

```
AWS_PROFILE=iam-admin ./ci/layer-upload.sh
```

### A brief digression into AWS Credentials

To get this stuff working locally you'll need the following in your
`~/.aws/config`:

```
[profile iam-admin]
sso_session = mozilla
sso_account_id = 320464205386
sso_role_name = AdministratorAccess
sso_region = us-west-2
region = us-west-2
sso_start_url = https://mozilla-aws.awsapps.com/start#

[sso-session mozilla]
sso_start_url = https://mozilla-aws.awsapps.com/start#
sso_region = us-west-2
sso_registration_scopes = sso:account:access
```

Every ~8 hours, run:

```
aws sso login --sso-session mozilla
```

## Test all Python modules

```
./ci/test.sh
```

## Deploying

*Deployments are manual, and ad-hoc*.

Each directory under `serverless-functions` represents something we're able to
deploy.

We have three stages:

* development;
* testing; and
* production.

If you wanted to deploy a new version of, let's say the
`identity_vault_curator`, you'd do:

```
cd serverless-functions/identity_vault_curator
AWS_PROFILE=iam-admin sls deploy --stage development --region us-west-2
```

*nb* The Layer ARNs for the "revived" builds are stored in a different AWS SM
Parameter.

* Old: `${ssm:/iam/cis/${self:custom.curatorStage}/lambda_layer_arn}`
* New: `${ssm:/iam/cis/${self:custom.curatorStage}/build/lambda_layer_arn}`

There are also some changes made to make calling `sls {deploy,info}` _slightly_
easier.

### A brief digression on serverless

You'll need to register an account on [Serverless]. From here, populate the
`SERVERLESS_ACCESS_KEY` environment variable with an Access Key. (Serverless ->
Organization settings -> Access Keys).

You may be able to run:

```
serverless login
```

As a sanity check, you should see something along the lines of:

```
# AWS_PROFILE=iam-admin sls info --stage development --region us-west-2

service: vault-curator
stage: development
region: us-west-2
stack: vault-curator-development
functions:
  ensure-vaults: vault-curator-development-ensure-vaults

```

If you don't see that, something's wrong.

[Serverless]: https://www.serverless.com/

# How changes are published to CIS

![Publisher](/docs/images/publisher_flow.png?raw=true "Publisher Diagram")

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

This is for local testing and development. This is also what is in the `master`
branch of this repository.

It uses a development set of keys for signing and verification. This
environment contains fake data and is neither persistent neither guaranteed to
be stable, though it should be almost always functional.

Access to this environment may be granted temporarily to diagnose specific
issues, features, etc. as they're being developed, but is not meant for general
QA.

URLs:
- https://change.api.dev.sso.allizom.org
- https://person.api.dev.sso.allizom.org
- https://auth.allizom.org/.well-known/mozilla-iam (contains all necessary information, URLs, audience, keys, etc.)

Audience:
- api.dev.sso.allizom.org

### Local development

We're moving towards having parts of this deployed to new infrastructure, to
overcome some limitations with our current setup. Namely, this is around a 30
second timeout, within the depths of our infra, that we're unable to change.

Some rough notes:

* `skaffold dev`, will build and test your container. You can access it by
  hitting `http://localhost:8000`.
* That's all! Currently working towards getting deployed into GKE.
* Credentials and further configuration is left as an exercise for the
  developer.
