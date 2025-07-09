resource "auth0_resource_server" "dev_sso_api" {
  identifier = "api.dev.sso.allizom.org"
  name       = "https://api.dev.sso.allizom.org"
}

resource "auth0_resource_server_scopes" "dev_sso_api" {
  resource_server_identifier = auth0_resource_server.dev_sso_api.identifier
  dynamic "scopes" {
    for_each = local.wellknown_scopes
    content {
      name        = scopes.value["value"]
      description = scopes.value["description"]
    }
  }
}
