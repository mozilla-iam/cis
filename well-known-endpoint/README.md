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
- `profile.schema` comes from CIS's `cis_profile` module, if you change it, change it in the module then copy it back
  here.

# Signed files

The well-known files are signed using infosec@mozilla.com's GnuPG/PGP key (0x2FC05413E11014B0DC658AD5956347F6FBF3A415).
The `make` target uploading the files verifies the files are correctly signed before uploading. If that's not the case,
you may need to regenerate the signature with `make sign`.


# Scopes in the authorizer / access provider

Scopes are declared here and used in code  The OAuth2 authorizer (here, Auth0) also needs to know about these scopes.
In order to deploy them easily, they're recorded in the `auth0_helper` directory and can be used directly with API
calls, until github.com/mozilla-iam/auth0-ci support this natively.

# Where does Mozilla run this?

Mozilla runs this in the IAM AWS environment: http://sso.mozilla.com/iam-infra
