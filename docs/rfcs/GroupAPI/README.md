# CIS Group API

The CIS Group API is an additional API for CIS that is specialized for managing user roles and groups.
It is used in addition to CIS's Profile v2 based API (Change, Person APIs).

While the CIS Profile v2 provides groups, it's very basic. CIS Group API proposes extensible, powerful groups. All APIs
use the same data sources and therefore present the same groups.

## CIS Profile v2 group structure

This is how CIS Profile v2 groups look like. They provide a unique name identifier and a description. The groups are
namespaced.

```
{
  ...
  "access_information": {
    "ldap": {
      ...
      "values": {
        "a_group_here": "description",
        ...
      }
  }
  ...
}
```

**NOTE**: The name identifiers (`a_group_here`) can be used to address group ids in the CIS Group API as well.

## CIS Group API structure

![cis_group_api](/docs/rfcs/GroupAPI/cis_data_table.png?raw=true "CIS Group API diagram")


## CIS Group API specification

- This is the [OpenAPI specification](/docs/rfcs/GroupAPI/group_api.yml)
- This is [a link to the Swagger editor](https://app.swaggerhub.com/apis/Mozilla-IAM/iam_group_api/1.0.0#/)
