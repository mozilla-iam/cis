# Settings for CIS

List of settings in AWS SSM for CIS.

NOTE: in case this is not up to date, please refresh this list. You can use something such as:

```
aws ssm describe-parameters --filters="Key=Name,Values=/iam/cis/development"|grep Name
```

To get an idea of what the list is.

# The list


NOTE: These are in the `/iam/cis/development` namespace. All these settings should also be available for other
environments (i.e. `/iam/cis/{testing,production}`).

# E2E Change client
Used for end to end (E2E) tests of the CI pipeline

- `/iam/cis/development/change_client_id`
- `/iam/cis/development/change_service_client_secret`
- `/iam/cis/development/change_service_signing_key`

## Signing Keys
These should be moved to their own function namespace over time

- `/iam/cis/development/keys/access_provider`
- `/iam/cis/development/keys/cis`
- `/iam/cis/development/keys/hris`
- `/iam/cis/development/keys/ldap`
- `/iam/cis/development/keys/mozilliansorg`

## LDAP Publisher
- `/iam/cis/development/ldap_publisher/bucket` The bucket where LDAP exports are stored
- `/iam/cis/development/ldap_publisher/bucket_key` The file name of the LDAP export
- `/iam/cis/development/ldap_publisher/client_id` Secrets for CIS API access
- `/iam/cis/development/ldap_publisher/client_secret`

## HRIS Publisher
- `/iam/cis/development/hris_publisher/client_id` Secrets for CIS API access
- `/iam/cis/development/hris_publisher/client_secret`
- `/iam/cis/development/hris_publisher/hris` The HRIS signing key
- `/iam/cis/development/hris_publisher/hris_password` HRIS credentials to fetch the report
- `/iam/cis/development/hris_publisher/hris_username`
- `/iam/cis/development/hris_publisher/hris_url` Where the report is located

## Change notification (webhook)
- `/iam/cis/development/webhook_notifier/client_id` Secrets for CIS API access
- `/iam/cis/development/webhook_notifier/client_secret`

## Misc
- `/iam/cis/development/lambda_layer_arn` The layer we're using, which includes our libraries.
- `/iam/cis/development/uuid_salt` A salt we're using to generate new `user.uuid` values


