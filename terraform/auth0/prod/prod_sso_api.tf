resource "auth0_resource_server" "prod_sso_api" {
  identifier = "api.sso.mozilla.com"
  name       = "https://api.sso.mozilla.com"
}

resource "auth0_resource_server_scopes" "prod_sso_api" {
  resource_server_identifier = auth0_resource_server.prod_sso_api.identifier
  dynamic "scopes" {
    for_each = local.wellknown_scopes
    content {
      name        = scopes.value["value"]
      description = scopes.value["description"]
    }
  }
}
