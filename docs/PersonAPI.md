# Using the CIS Person API endpoint

## What is CIS Person API?

The CIS (Change Integration Service) Person API is a read-only API to get access to the user database (Vault).

This is CIS Person API v2 (version 2).

## What are the access controls around CIS Person API?

CIS Person API requires credentials for most routes (i.e. all routes that may expose non-PUBLIC data).
It leverages Mozilla's [data classification](https://wiki.mozilla.org/Security/Data_Classification) to decide which kind of data is to be returned, and will filter out anything
that does not match the classification levels you have been granted access to.
Data is also filtered by something we call a display level, which is the level a user request the data to be filtered at, for displaying purposes.

In other words, the data `classification` is used to decide which data can be sent to machines, the `display` level is used by machines to decide if the data can be shown to other users (i.e. while they have access to it).

You can check which fields of a user can be accessed with which classification here:
https://auth.mozilla.com/.well-known/profile.schema (or in
[cis_profile](../python-modules/cis_profile/cis_profile/data/user_profile_null.json) which can be slightly easier to
read. Pro-tip, you can load this in a JSON viewer (Search for JSON viewer on the web).


### How are scopes used?
NOTE: `classification:public` is default is always granted, even if no scope is present. This allows unauthenticated endpoints to query public data. The same is not true for `display:public`.

#### Full list of scopes:
The scope list is also available [here](../well-known-endpoint/auth0-helper/scopes.json).

```
classification:public
classification:workgroup (non-public data)
classification:workgroup:staff_only (Staff data)
classification:mozilla_confidential (staff or/and NDA'd data)
classification:individual (Individual confidential data - most sensitive)
display:none (fields that do not use the display levels such as `user_id` - this scope is necessary to get them!)
display:public
display:authenticated (user indicate this is to be shown only to users that are authenticated with the system)
display:vouched (user indicate this is to be shown to vouched profiles only)
display:staff (user indicate this can only be shown to Mozilla staff)
display:private (user indicate this should not be shown to any user, only machines/API should see it)
display:all (overrides all display levels)
read:fullprofile (overrides all classification levels)
write (scope for CIS Change API which allows profile writes. Note that your signatures still need to match a trusted publisher, and that this scope alone is not sufficient to write data to the API - on it's own it effectively does not grant write access)
```

#### Access all public data and workgroup confidential fields that the user expressedly indicated can be shown publicly
```
classification:public
classification:workgroup
display:none
display:public
```
Same, but also get data that the user wants to be only shown to other authenticated users, if you chose to display it back.
```
classification:public
classification:workgroup
display:none
display:public
display:authenticated
```

#### Access all staff data (office location, desk number, team name, users who do not want their name to be public but are staff, etc.)
```
classification:public
classification:workgroup:staff_only
display:none
display:public
display:authenticated
display:vouched
display:staff
```

#### Access all data (dangerous! this will usually not be granted)
```
read:fullprofile
display:all
```

## How do I get credentials for access?

Please file a request at https://mozilla.service-now.com/sp?id=sc_cat_item&sys_id=1e9746c20f76aa0087591d2be1050ecb

Indicate your use case, and the fields you need to access and/or their data classification and display level.

For example:

> I need access to the office location of all employees (`classification:workgroup:staff_only`, `display:staff`) so that I can send messages about when
> their office will be closed during the holidays.


Depending on the request, it's possible that we follow-up with a rapid risk assessment
(https://infosec.mozilla.org/guidelines/risk/rapid_risk_assessment), or simply grant the access.


NOTE: **If no use case or user story with a rational is present, no access will be granted to NON-PUBLIC data!**


The credentials you will receive are OAuth2 credentials.

## Do you have code examples?

Yes, please look at our [end to end (E2E) tests](../e2e).

As well, here is a [simple golang client library](https://github.com/mozilla-services/foxsec-pipeline-contrib/tree/master/common/persons_api).

Here's a quick curl example as well:
```
# Get a token
$ curl -X POST -H "Content-Type: application/json" https://auth.mozilla.auth0.com/oauth/token -d \
'{"audience":"api.sso.mozilla.com","scope":"classification:staff_confidential display:staff",\
"grant_type":"client_credentials","client_id": "YOUR CLIENT ID", "client_secret": "YOUR CLIENT SECRET"}'

# Use the token
$ curl -H  "Authorization: Bearer YOUR_TOKEN_HERE" https://person.api.sso.mozilla.com/v2/user/primary_email/some_email@email.com
```

## What is the API URL?

You can find it here: https://auth.mozilla.com/.well-known/mozilla-iam (look for person api).

## What routes are available? (i.e. what queries can I make)

The easiest is to mimic the E2E tests, otherwise:

Retrieve specific user profiles. By default these only includes active users:
- `/v2/user/user_id/<string:user_id>`
- `/v2/user/uuid/<string:uuid>`
- `/v2/user/primary_email/<string:primary_email>`
- `/v2/user/primary_username/<string:primary_username>`

Retrieve paginated list of all user profiles. By default this only includes active users:
- `/v2/users`

In this case you will receive a JSON document such as :
```
{
  "Items": [profile_1, profile_2, ...],
  "nextPage": None
}
```
where `nextPage` will be set to a `user_id` if there are more pages to fetch.

To fetch the next page simply call:
- `/v2/users?nextPage=user_id_here`

Until `nextPage` is set to `None`.

Retrieve lists of users (not full profiles):
- `/v2/users/id/all?[connectionMethod=ad]` (Returns all user ids for a specific login/connection method) By default this only includes active users.

- `/v2/users/id/all?[connectionMethod=ad&active=True]` (Returns all user ids for a specific login/connection method showing only active user IDs) **Highly Advised**

- `/v2/users/id/all?[connectionMethod=ad&active=False]` (Returns all user ids for a specific login/connection method that are currently marked inactive)

*Note true/false are case insensitive for ease.* 


## I want to help add features to this API!

Hey, that's great! Please look at [cis_profile_retrieval_service](../python-modules/cis_profile_retrieval_service) and send
us a PR!


# FAQ (Frequently Asked Questions)

- I updated my name in the old Phonebook but the change does not appear in CIS Person API, why is that?
CIS will allow certain publishers to write the attribute when the user is created, but not update it. Preferred names for example are created by LDAP (old Phonebook) but then owned by Dinopark. Once created, these can only be modified by DinoPark.
When the old Phonebook is retired, this will no longer be an issue.

- How often is the user profile data refreshed by publishers?
CIS uses a batch-and-event model, which means certain changes happen very quickly (seconds) as an event occurs, while other changes may take longer (batches every 5,10,15 minutes for example).
All writes should attempt to use both batch and event, to provide the best mix of latency and reliability.
