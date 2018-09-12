# cis_crypto

The CIS Crypto library supports all sign/verify operations for files, profiles, and attributes in mozilla-iam.  
It is meant to be one component in a loosely coupled signing system leveraging jwks/RS256.

## Dependencies

* Mozilla-IAM .well-known endpoint

## Development Instructions

Since not all modules are published to python-warehouse yet you'll need to install the cis_fake_well_known module
and cis_aws module by hand.  With your virtual environment and also inside the `cis_crypto` directory simply type:

```bash

python ../cis_aws/setup.py install
cd ../cis_fake_well_known/ && python setup.py install && cd -

```

## Setup for Signing Keys

1. Generate an RSA KeyPair and place the private key material in aws-ssm parameter store.
Name the key `/iam/access-key-file`.

2. Place the public key material within the location of the .well-known mozilla file.  Note: this does not exist yet at the time of writing.


## How to Sign a File

1. Install this python module.

2. Place a .mozilla-cis.ini in your home directory and set the following values related to signing.

```
Cryptography Settings for sign-verify operations
secret_manager=aws-ssm # Can be file or aws-ssm
cis_well_known_url=https://auth.mozilla.com/.well-known/mozilla-iam
cis_well_known_mode=file # Can also be http if you want to use the well known endpoint above.
cis_public_key_name=fake-access-file-key # Optional for use with file mode only.

## AWS Specific Secret Manager Settings
secret_manager_ssm_path=/iam
secret_manager_ssm_region=us-west-2

# give the name of the key without file extension that you would like to sign assertions with
signing_key_name=access-file-key
```

Assume a role in the AWS account that has access to the key material.  At the time of writing apps.yml key material is in infosec-dev for auth0-staging and infosec-prod for auth0-production.

3. Sign the file.

```bash

cis_crypto sign --file apps.yml
2018-08-28T09:21:57 - cis_crypto - INFO - Attempting to sign file: apps.yml
2018-08-28T09:21:57 - cis_crypto - INFO - File signed.  Your signed file is now: apps.yml.jws
2018-08-28T09:21:57 - cis_crypto - INFO - To verify this file use cis_crypto verify --file apps.yml.jws

```
