# Sample Publisher
Demonstrate a sample flow of using the cis_dev_preview docker container.

## Running this sample code against the single container environment.

1. `make docker-build`
2. `make docker-run` # this will up the dev preview bound to localhost.

## Endpoints provided in the developer preview
```
http://127.0.0.1/change
http://127.0.0.1/change/status?sequenceNumber=123456
http://127.0.0.1/v2/user/user_id
http://127.0.0.1/v2/user/uuid
http://127.0.0.1/v2/user/primary_email
http://127.0.0.1/v2/user/primary_username
http://127.0.0.1/v2/users
http://127.0.0.1/.well-known/mozilla-iam
```

## Developer preview uses the following features

1. stream bypass... changes are simulated and written directly to dynamodb
2. no_signature checks.  Publishers are only required to assert the appropriate name.
3. no bearer token validation.  APIs require the correct scopes but the token need not have valid signatures.
4. seed identity vault.  On initialize the identity vault will have 100 fake users in it to start.
5. dev preview is a single flask thread per process.  production will be much faster and support batches of profiles to /change
6. running py.test in the sample-publisher project will effectively run an end to end test of the endpoints.

## Basic publisher flow.  
1. publisher loads the profile from whatever data store.
2. publisher puts the profile in profilev2 format for the fields _it_ is allowed to publish.
3. publisher queries the person-api to see if the user already exists and integrates any fields it is not authoritative for without modification.  If this is a new user the publisher should new up a user skeleton using cis_profile.User() and update it's fields then publish.  Empty fields will be asserted as null and this will pass.
4. publisher uses their publisher-key.pem from somewhere to sign the fields they assert using cis_profile sign/verify methods.  _please don't re-implement your own signing in python.  crypto is hard._
5. publisher POST to /change endpoint with the json payload.  If the schema is valid the publisher will receive a sequence number in exchange.
6. In production the message would enter kinesis, signatures and publisher authority will be checked, then integrated.  In development the messages will use a mocked kinesis to generated a sequenceNumber and bypass directly to dynamodb without these tests to facilitate connector development.  __Future:__ add an option to test the publisher rules using cis_profile here if there is no performance impact.
7. The publisher can poll the `/change/status?sequenceNumber` endpoint to see if the message has been integrated.  The change should be integrated in < 1 second or the integration should be considered to have failed and needs to retry. __Future:__ replaced/supplemented by supporting a webhook back. 
8. Finally the `/v2/user/user_id/<string:user_id>` endpoint can be queried to see the fully integrated profile.


## Recommended pattern

```
# New up your objects outside of loops for optimized caching
profilev2 = cis_profile.profile.User()

# read your data source: hris, etc...
some_data_i_got_from_json = json.loads(some_data_from_somewhere)

for users in some_data_i_got_from_json:
  profilev2.user_id.value = some_data_i_got_from_json['arbitrary_key']['value']
  profilev2.access_information.mozilliansorg.values['nda'] = None
  profilev2.update_timestamp('user_id')
  profilev2.update_timestamp('access_information.mozilliansorg')
  profilev2.sign_attribute('user_id')
  profilev2.sign_attribute('access_information.mozilliansorg')

  # Validate our change before sending ( doe not check publisher or signature )
  profilev2.validate()
  # use request to publish this to the /change endpoint
  # log the sequence numbers to a list or something


check the status of our integrations
return statuses

```
