# Files here that are authoritative (i.e. source of truth)

- user_profile_null.json - a demo empty profile which is also used to create the objects dynamically
- profile.schema - THE profile schema

# Files here that are cached copies and may get out of date

Always modify the original, not these copies!
Always attempt to copy over the original here, these are last-resort-fallback when online copies are unreachable.

- mozilla-iam (see [well-known-endpoint](../../../../well-known-endpoint))
- mozilla-iam-publisher-rules (see [well-known-endpoint](../../../../well-known-endpoint))


# How to change the profile schema?

- update data/profile.schema
- update data/user_profile_null.json
- update data/well-known/mozilla-iam-publiser-rules
- update CIS's well-known endpoint repository with these files as well (cis/well-known-endpoint)
- Ensure all tests run of course
