# Access File

## Summary
Mozilla IAM validates identity using one or more factors. It also validates authorization, or access, using one or more authorization stages. The common case is a user account's access being verified by the access provider at a high-level using broad groups or roles. The RP (Relying Party) will then perform the same or/and additional verification, which may allow specific access within the application.

Ex: A reviewer may have a 'Staff' role and is granted access at the first stage verification. The reviewer then gets access to the reviewer features in the application, access which is granted by the 2nd stage verification (i.e. RP verification).

![2stages](/docs/images/2stageaccess.png?raw=true "2 Stages Access Diagram")

The *Access File* is the file that contains the access decision data for the first stage (stage 1) (https://cdn.sso.mozilla.com/apps.yml)
It is publicly available on [GitHub](https://github.com/mozilla-iam/sso-dashboard-configuration/blob/master/apps.yml).

## High level security requirements

The Access File may only be modified by authorized personnel. In order to verify it's authenticity and integrity:

- All changes must be done using signed commits and these commits required by the SCM or CI (in particular if CI is also
  signing the Access File before publishing).
- All changes must be peer reviewed before being published to the production systems.
- The file must be signed by a trusted and verifiable authority.
- Any error while parsing the Access File must deny access for the users.

### Threats discussed

1. Authorized personnel compromise (laptop, etc.)

In this case, the attacker has access to the GnuPG commit signing key and is able to commit changes to the repository,
though is not able to directly upload the changes to production as peer review is required.

2. CI or SCM compromise

In this case, the attacker is able to upload changes to production and sign the file, though the attacker may not sign
commits.
It is recommended to verify commits signatures and integrity of the Access File externally in order to detect a CI or
SCM compromise.

3. CDN compromise

In this case the attacker is able to upload changes to production but not sign them. Consumers of the file will fail
signature verification and accesses will be denied.

4. Access File parsers compromise

In this case, all bets are off as the attacker controls the decision facility and can bypass the Access File. For
example if the access provider (such as Auth0) is compromised, the parser and decision facility would be compromised.

## Access File parsers security requirements

An Access File parser is code that will download and interpret the Access File in order to grant or deny accesses for
users. For example the access provider (such as Auth0) runs a parser for stage 1 access verification.

- The parser must deny access if:
  - Any parsing error occurs.
  - The Access File cannot be retrieved.
  - The signature validation fails.

- The parser must also:
  - Always validate the signature of the Access File.
  - Never cache the Access File for longer than 5 minutes (i.e. access changes will be live within 5 minutes).


## Access File format

This is a YAML file with a list of applications (Relying Parties) as such:

```
---
apps:
  - application:
      name: "Example"
      client_id: "xzc2030239xzxc"
      op: auth0
      url: "https://rp.example.net/"
      logo: "example.png"
      authorized_users: []
      authorized_groups: []
      expire_access_when_unused_after: 7776000
      display: true
      vanity_url: ['/an-easy-to-remember-url']
  - applicatiom:
      ...
```

**name**: A name for the relying party.
**client_id**: The access provider or OpenID Connect provider identifier for this relying party.
**op**: The access provider (Openidconnect Provider) name.
**url**: The canonical URL for the relying party.
**logo**: An image with the relying party logo.
**authorized_users**: A list of users that are authorized to login to the relying party. If empty, this is not used.
**authorized_groups**: A list of groups that are authorized to login to the relying party. If empty, this is not used.
**expire_access_when_unused_after**: The time, in seconds, after which access will be denied for a user of this relying
party. This is taken into account after the user's first login, and is reset every time the user login to this relying
party.
**display**: If true, the relying party will be displayed on the SSO Dashboard (https://sso.mozilla.com)
**vanity_url**: A list of easy to remember URLs for the SSO Dashboard, that a user can bookmark to access the relying
party.

## Notes on access attributes

### authorized_users and authorized_groups

When the field is empty the parser considers that all users *or* groups are allowed in. If it's not empty, only the
listed users *or* groups are allowed in.
Note that if neither fields are empty, users that are *NOT* in the listed groups **will be allowed in**.

Example scenarios:

1. Access is always granted:

```
authorized_users: []
authorized_groups: []
```

2. Only specific users can access:

```
authorized_users: ['user1', 'user2']
authorized_groups: []
```

3. Only specific groups can access:

```
authorized_users: []
authorized_groups: ['group1', 'group2']
```

4. Specific groups can access, in addition to specific whitelisted users which can also access:

```
authorized_users: ['luckyuser`]
authorized_groups: ['group1', 'group2']
````

### expire_access_when_unused_after

This field requires specific implementation in the access provider's parser, which remembers the last time a user has
logged in. If the user does not login again during the *expire_access_when_unused_after* time (in seconds), the user
will be denied access to the relying party the next time they login and will need to ask for their access to be
re-established.

If the user login regularly, the access will be maintained.

More information on the implementation can be found
in [AutomaticAccessExpiration.md](rfcs/AutomaticAccessExpiration.md)

## Notes on the access provider implementation (Auth0)

The parser can be found here: https://github.com/mozilla-iam/auth0-deploy/blob/master/rules/AccessRules.js
The parser logs errors to Auth0 rule logs, which are Webtask logs. These can be viewed by the Webtask tools such as
[wt-cli](https://github.com/auth0/wt-cli). Information on how to setup wt-cli can be found at https://auth0.com/blog/troubleshooting-webtasks-using-the-cli/
