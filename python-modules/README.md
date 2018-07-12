# Mozilla Change Integration Python Modules

Mozilla IAM uses a variety of Python modules to achieve integration in what we call CIS (Change Integration Service).  In version 1 of the change integration service one library formerly known as `cis` held all this functionality.

In version 2 of this service, the separation of concerns requires a more loosely coupled approach.

## Definitions

- (Stream) **publisher**: An entity which publishes changes to user profiles (i.e. updates a user profile attributes and request these to be integrated).
- (Stream) **processor**: An entity which reads the latest changes sent by a publisher and replicates them where necessary.
- (Stream) **worker**: A type of *processor* which manages, validates, etc. change messages.
- **Authorizer**: The OAuth Authorizer which exchanges access tokens, granting access to endpoints (provided by Auth0 here).
- **CIS**: Change Integration Service, this service.

## Modules in this directory

**cis-common**

Code that is common to all additional libs.  Configuration management, authorization layers, etc.

_User Stories_

- As a publisher I must exchange a `CLIENT_ID` and `CLIENT_SECRET` with the OAuth authorizer for an access token.  This grants the ability to publish changes.
- As a processor I must exchange a `CLIENT_ID` and `CLIENT_SECRET` with the OAuth authorizer for an access token.  This grants the ability to write profiles to auth0.
- As a developer I need a way to override standard configuration variables using a pyconfig, an environment variable, etc.

**cis-aws**

Contains all the code necessary for role assumption in the target AWS account which holds CIS data, enumerating dynamodb-tables, enumerating kinesis streams, sending to kinesis, and writing to dynamodb.

_User stories_

- As an stream woker working with the change integration service in order to publish profiles I need to assume a role.
- As a stream processor in order to publish profiles I must enumerate dynamodb tables and target the appropriate table using tags.
- As an API endpoint publishing changes I must target kinesis streams to send profiles through the system.
- As an API endpoint I need to publish profiles to a kinesis stream and validate the message was sent.
- As a stream worker signing and verifying message I need to retrieve private keys from AWS parameter store.

**cis-crypto**

Contains all logic for retrieving JWKS information both public and private.  Allows abstraction of `.well-known` URLs to config parameters.  Support sign verify operations.

Depends on: cis-aws for retrieval of secrets for key material.

_User Stories_

- As a publisher I need the ability to sign attributes using JWKS.
- As a processor I need to verify per profile signatures and raise an exception if the profile signature is not valid.
- As a processor and publisher I need to discover public key material at configurable `.well-known` URLs.

**cis-identity-vault**

Contains all code for the formation of the identity vault and management there-of.  Not related to cis-aws.  This module use pynamodb as a means of describing the user profile schema and creating the table with the appropriate tags.  

_User Stories_

- As an IAM admin I can create mozilla-iam profile v2 identity vaults.
- As an IAMdeveloper I can import the pynamodb schema into other classes for use in applications like graphql.

**cis-processor**

Contains basic business logic code for working with batches of profiles entering and exiting the stream.  

Depends on:

* cis-aws
* cis-crypto

_User Stories_

- As a processor I need to retrieve batches of profiles from the kinesis stream.
- As a processor I need to receive batches of profiles from the DynamoDb streams.
- As a processor I need to continue processing all profiles in a batch even if a single profile fails.
- As a processor I must log any actions taken on a user profile to a consolidated logging mechanism.

**cis-publisher**

Contains all logic for web properties that publish profile changes to the change integration service stream.  Send an event, check status of event are core functions for this lib.

Depends on:

* cis-crypto

- As a publisher like mozillians.org I need to send a profile change and receive an ID for the change record.
- As a publisher like mozillians.org I need to know the status of a single event and if it failed or succeeded.
- As a publisher I need to sign individual user attributes in addition to full profiles using JWKS.

**cis-logging**

Contains all code needed to support the output of logs to Cloudwatch consolidated logging.  Provides a `streamHandler` interface and centralized configuration for `DEBUG`, `INFO`, etc.

**cis-fake-well-known**

Contains faking functionality and a dummy server to provide JWKS key material for testing sign/verify operations.

_User Stories_

- As a developer I need a way to retrieve `.well-known` configurations prior to the data being available on auth.mozilla.com

**cis-fake-change-service**

Contains a dummy server that provides mocked responses identical to sending a message successfully to the kinesis stream.

## Requirements for Development

* All modules will use pytest for testing.
* All modules will declare production requirements in setup.py pinned to specific versions.
* Pipenv files will be provided for all modules.
* All modules with achieve ~ 80% coverage.
* All coverage tests will run offline.
* Modules will only support Python 3 or greater.
* Publisher / processor modules will expose a common business object layer in the form of a standardized object used in batch processing.
* Authorizer exchanges for access tokens tokens will happen outside of batch processing to reduce the use of tokens.
