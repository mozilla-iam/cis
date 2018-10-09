# CIS - Change Integration Service

# THIS IS A WIP BRANCH FOR PROFILE v2

This is a work in progress for updating docs and design concepts for profile v2.  Things may not all be updated as yet.

## Documentation & Resources

- [CIS Person-API](https://github.com/mozilla-iam/person-api)
- [CIS Security](docs/Security.md)
- [CIS Event format for publishers](docs/Event.md)
- [User Profiles](docs/Profiles.md)

## Draft-RFCs & Proposals (informational-only)
- [RFCs preamble](docs/rfcs/README.md)
- [API](docs/API.md) (Now Person-API)
- [Automatic Access Expiration](docs/AutomaticAccessExpiration.md)
- [User profile v2](docs/rfcs/UserProfilesv2.md), [User profile schema v2](docs/rfcs/UserProfilesv2_schema.json)

## Summary

CIS is the Mozilla IAM Change Integration Service.

This is a stream-based system that validates user identity-{change,creation,etc} events from a set of event
`publishers`, stores the resulting user database in what we call the `identity vault`, and provision or signals
consumers through what we call `identity drivers`.

Example: Mozillians.org user profile editor sends a modified t-shirt size for
user A to CIS. CIS validates the change, stores it in the `identity vault` and
triggers updates to Auth0, LDAP, etc.

![Publisher=>CIS Vault=>ID Driver](/docs/images/CIS-AWS-Stencils.png?raw=true
"CIS Diagram")

## Technologies

- Stream Publishers (sends identity change events to CIS): Python lambda
  functions
- Stream Identity Drivers (deliver/propagate identity changes from CIS): Python
  lamba and webtask functions
- Identity Vault (source of truth for identity data): AWS DynamoDB
- Stream itself: AWS Kinesis

See also <https://github.com/mozilla-iam/cis_functions/> to find the serverless
code of the stream publishers/identity drivers.
