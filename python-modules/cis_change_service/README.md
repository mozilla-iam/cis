# cis_change_service

Python flask application delivered as a python package for accepting changes to the change integration cis_change_service version 2.  

## Endpoints

* /change
* /status

** Usage **
```
result = self.app.post(
    '/change',
    headers={
        'Authorization': 'Bearer ' + token
    },
    data=json.dumps(user_profile),
    content_type='application/json',
    follow_redirects=True
)
```
Response should contain a change_id that can be used to query the status endpoint.  In future will support webhook
registration.

```
status_endpoint_result = self.app.get(
    '/change/status',
    headers={
        'Authorization': 'Bearer ' + token
    },
    query_string={'sequenceNumber': response.get('sequence_number')},
    follow_redirects=True
)
```
Returns True or False for the integration.
