resource "auth0_resource_server" "test_sso_api" {
  identifier = "api.test.sso.allizom.org"
  name       = "https://api.test.sso.allizom.org"
}

resource "auth0_resource_server_scopes" "test_sso_api" {
  resource_server_identifier = auth0_resource_server.test_sso_api.identifier
  dynamic "scopes" {
    for_each = local.wellknown_scopes
    content {
      name        = scopes.value["value"]
      description = scopes.value["description"]
    }
  }
}
