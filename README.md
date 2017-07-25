# CIS - Change Integration Service

## Summary
Home of Mozilla IAM change integration service repository.
This is a stream-based system that validates user-{change,creation,etc} events from a set of event `publishers`, stores 
the resulting user database in what we call the `identity vault`, and provision or signals consumers through what we
call `identity drivers`.

Example: Mozillians.org user profile editor sends a modified t-shirt size for user A to CIS. CIS validates the change,
stores it in the `identity vault` and triggers updates to Auth0, LDAP, etc.

## Technologies

- Stream Publishers (sends identy change events to CIS): Python lambda functions
- Stream Identity Drivers (deliver/propagate identity changes from CIS): Python lamba and webtask functions
- Identity Vault (source of truth for identity data): AWS DynamoDB
- Stream itself: AWS Kinesis

See also https://github.com/mozilla-iam/cis_functions/ to find the serverless code of the stream publishers/identity drivers.

## Diagram of functionment

![Publisher=>CIS Vault=>ID Driver](/docs/images/CIS-AWS-Stencils.png?raw=true "CIS Diagram")
