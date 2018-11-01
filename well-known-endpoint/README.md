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
