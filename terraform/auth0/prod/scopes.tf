locals {
  wellknown_scopes = jsondecode(file("../../../well-known-endpoint/auth0-helper/scopes.json"))["scopes"]
}
