resource "auth0_resource_server" "test_sso_api" {
  identifier = "api.test.sso.allizom.org"
  name       = "https://api.test.sso.allizom.org"
}
