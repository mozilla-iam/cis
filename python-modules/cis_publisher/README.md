# cis_publisher

Library module used by publishers to CIS.

It takes a CIS profile object (`cis_profile.User`) that is well-formatted and valid, then:
- ensures it has all required attributes (`active`, `user_id`, `primary_email`) (note that `uuid` and
  `primary_usernames` are set by `cis_change_service` and therefore not required here)
- validates the profile (signature, publishers, schema)
- Post it to the `cis_change_service` API
- Auto-retry on failure (with delay) a few times

It does not:
- cache user profiles
- support event-based publishing (at this time)


It aims to be run as a serverless function every X amount of time.

## HRIS

If any warning, critical or error message is issued by the HRIS publisher and it's relevant to the data source, please
contact `hrisintg [_AT_] mozilla.com`
