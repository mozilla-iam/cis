# CIS / Terraform

* `build`: AWS resources to facilitate building.
* `auth0`: Auth0-related resources. CIS is the source of truth
  for these resources, so it's best (for locality) they live here.

## Disclaimer

DEBT(bhee): There's now a _bunch_ of different places we have Terraform.
There's been _some_ effort to centralize where, but I'm making an explicit call
to keep CIS-related things in the CIS repository.

This almost follows the pattern from dino park, except we also have
mozilla-iam/iam-infra.

There is no right decision here, only less wrong; and this is the one I made.
