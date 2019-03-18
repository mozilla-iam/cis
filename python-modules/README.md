# Mozilla Change Integration Python Modules

- CIS, CIS API: Change Integration Service, this service.
- CIS Person API: The read-only part of the CIS API.
- CIS Change API: The write-only part of the CIS API.
- CIS Vault: The database which contains users in CIS.
- CIS Publisher: An entity which uses the CIS Change API to propose changes (new users, updates, etc.)
- Display: A user-preference for displaying user profile fields in DinoPark (or other RPs which decide to use this value.)
- Classification: A data classification for user profile fields which is used to determine which fields can be sent to
  which RPs. If your RP does not have the right classification access, it will not see fields with that classification.
- E2E Tests: End to end tests, which connect to a live CIS environment to perform tests.


See also the main README for more information.

## Modules

NOTE: Each module may also have it's own, more detailed README.md file.

### Dependencies
These are modules that are primarily used by other modules.

#### cis_aws
This module provides common functionality to access AWS.

####  cis_crypto
This module provides crypto primitives, it retrieves keys, signs, verify blobs of data.

#### cis_identity_vault
This module provides an interface to DynamoDB where users are stored, i.e. the CIS Vault.

#### cis_profile
This module provides all primitives to process, verify, sign, user profiles. It also contains an interface to the
Mozilla IAM well-known endpoint.

### API Modules

#### cis_change_service

The CIS Change API. It takes user create or modification change requests, validate them (signature, publishers) and
update the CIS Vault accordingly. It also triggers the `cis_notifications` service.

#### cis_profile_retrieval_service

This CIS Person API. It is used to read users and user data.

#### cis_notifications

This module triggers notification via WebHook to publishers or RPs that need to be informed about changes on a user in
an event-based model.

#### cis_publisher

This module contains publishing code for several CIS publishers. CIS publishers call the `cis_change_service` and create
or update users based on their own database (e.g. LDAP publisher, HRIS publisher, etc.)

Note that the DinoPark/Mozilliansorg publisher is not stored in this repository.

## Rules and principles for development

* All modules use tox pytest for testing.
* All modules declare production requirements in setup.py.
* All modules aim to achieve ~ 80% test coverage.
* All coverage tests will run offline.
* Modules only support Python 3 or greater.
* All modules use a centrally configured logger.
