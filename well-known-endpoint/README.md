# Well-Known Endpoint

A well-known endpoint is an URL that lives under https://example.net/.well-known/
It is well-known by the consumers of that endpoint and generally lists parameters, public keys, etc. to use a specific
service.

See also:
- [RFC 5785](https://www.ietf.org/rfc/rfc5785.txt)
- [Well-Known Endpoint CIS documentation](../docs/Well-known Endpoint.md)
- [Endpoint source files](./s3)

# How to

Type `make` for a list of targets.
Use `pem_to_jwks.py` if you need to convert PEM pubkey files to JWKS (useful when first generating the keys from openssl for
example)

# About `s3` and `tpl`

- `tpl` contains the original templates for the files, CHANGE THESE!
- `s3` is where the templates are copied after changing their values depending on the environment, DO NOT CHANGE THESE!

# Where does Mozilla run this?

Mozilla runs this in the IAM AWS environment: http://sso.mozilla.com/iam-infra
