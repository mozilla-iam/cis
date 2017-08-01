# Publisher event format

Or how to send an identity event that CIS will correctly validate and understand.

## Publisher key and CIS stream access

A publisher key is assigned to your publisher when you register with CIS.
Registering with CIS is a manual step and must be requested to the
[Mozilla IAM](iam@mozilla-community.org) team.

The key is used to decide which additional validation will be performed and
which fields and attributes your publisher is authorized to modify.

A validation plugin must be written for your publisher.

## What to send to the stream

Stream events need to contain three primary keys in order to process properly.  ( _Note that the CIS core library does not currently reflect this_ )

* Publisher used as partition key
* Signature (TBD) but field must be present
* Profile

__Sample__

``` javascript
event : {
  'profile': {},
  'publisher': {},
  'signature': {}
}
```

* The profile contains the user-profile change.
* Publisher uniquely identifies the publisher.  Example: mozillians.org
* Signature is a KMS encrypted payload for
validating the payload or profile has not been tampered with in transit.  This signature is generated and validated using [pykmssig](https://github.com/mozilla-iam/pykmssig/)

## JSON user profile ('user identity')

- [Profile schema](/cis/schema.json)

The entire profile must be sent to CIS. It is either created from scratch for
new users, or fetched from an identity provider such as Auth0, then modified
and sent back to CIS in it's entirely.  Any missing field that your publisher
is responsible for will cause a validation error that will reject the complete
change.

### User profile signature

All user profiles submitted to CIS must be signed with your unique and private
publisher key.
Signing uses https://github.com/mozilla-iam/pykmssig/ and the signature is sent
in a separate JSON document.
