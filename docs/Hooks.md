# CIS Notifications

Change Integration Service version 2 features outbound hooks to notify relying parties that the user
profile may have changed.

## Basic Flow 

The basic flow is as follows.

1. Publisher triggers an authenticated update.
2. It is written to the Dynamodb table using dynamodb transactions. 
3. An event is generated to a dynamodb stream.
4. A webhook service iterates through the single sharded/single partition stream in batches of 10 users.
5. A request payload is generated that contains the following information.
```
    {
        "operation": update,
        "id": ad|Mozilla-LDAP|dinomcvouch,
        "time": {epoch timestamp},
    }
```
6.  The webhook service calls auth0 and signs an authenticated JWT for the API Aud: hook.{prod|dev|test}.{sso.allizom.org|sso.mozilla.com}.
7.  The payload is then posted to all configured relying parties.  These RPs can choose (strongly reccomended) to authenticate the inbound notification using standard JWT verification with the auth0 .well-known metadata.

## Requesting Additional Hooks 

Talk to @akrug on mozilla slack.