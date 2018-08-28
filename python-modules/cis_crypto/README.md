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
