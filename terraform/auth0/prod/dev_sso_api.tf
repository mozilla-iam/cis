resource "auth0_resource_server" "dev_sso_api" {
  identifier = "api.dev.sso.allizom.org"
  name       = "https://api.dev.sso.allizom.org"
}
