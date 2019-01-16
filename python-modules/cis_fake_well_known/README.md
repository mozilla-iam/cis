# cis_fake_well_known python module

## Purpose

The purpose of this module is to provide mocks of the "well-known-endpoint" structure as described [here]('https://github.com/mozilla-iam/cis/blob/profilev2/docs/Well-known%20Endpoint.md').  This will facilitate
rapid development of the modules cis_crypto, cis_publisher, cis_processor, and cis_fake_change_service.

## Setup

This requires a mozilla-cis.ini file to be places in one of the standard locations:

* `/etc/mozilla-cis.ini`
* `~/.mozilla-cis.ini`

Or environment variables can alternatively be set for the values required.

## Usage

The module can be used in one of two ways.  

* Direct import
* Run a web server


### Standard Flask App Spin Up
Upon pip installing a bin/ wrapper has been provided to spin up the flask app.

```bash
(env) akrug:cis_fake_well_known akrug$ cis_fake_well_known
 * Serving Flask app "cis_fake_well_known.app" (lazy loading)
 * Environment: production
   WARNING: Do not use the development server in a production environment.
   Use a production WSGI server instead.
 * Debug mode: off
 * Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)
127.0.0.1 - - [01/Aug/2018 08:24:51] "GET /.well-known/mozilla-iam HTTP/1.1" 200 -
```

### Leveraging in another test pipeline
The module is importable without spinning up the flask wrapper.  Though the flask wrapper will likely be quite handy
for development in languages not python3.  Here's an example of the two primary features that can be used in another test
pipeline to get the correct key material forms.

```python

from cis_fake_well_known import well_known

well_known_object = well_known.MozillaIAM()

# This method provides everything that is available on the public endpoint.
well_known_data_structure = well_known_object.data()

```

#### Returning key material

The faker class also supports returning different forms of the private key material.

```python

from cis_fake_well_known import fixture

fixture_object = fixture.Key()

fixture_object.available_keys()

# Returns a list of the keys the faker module is aware of.
['fake-publisher-key_0.pub.pem',
 'fake-publisher-key_1.pub.pem',
 'fake-access-file-key.priv.pem',
 'evil-signing-key.pem',
 'fake-publisher-key_0.priv.pem',
 'fake-publisher-key_1.priv.pem',
 'fake-access-file-key.pub.pem']

 # These can be loaded in different forms using the Key() object.

fixture_object = fixture.Key(
  key_name='fake-publisher-key_0',
  key_type='priv',
  encoded=True
)

fixture_object.material # This is an object property

{'alg': 'RS256',
 'kty': 'RSA',
 'n': b'vETmzgak....',
 'e': b'AQAB',
 'd': b'LMVx4bLAzwsl...',
 'p': b'26_zY...',
 'q': b'22N-fpJbM-...',
 'dp': b'243mMWrU...',
 'dq': b'He4z-rai...',
 'qi': b'OBNvhuUQ...'
 }

# Returns a jwks standard dict()

fixture_object = fixture.Key(
  key_name='fake-publisher-key_0',
  key_type='priv',
  encoded=False
)

# If encoded is set to false this will return the bytes type form of the pem.

fixture_object.material

 b'-----BEGIN RSA PRIVATE KEY-----\nMIIEogIBAAKCAQEAvETmzgak...=\n-----END RSA PRIVATE KEY-----\n'
```
