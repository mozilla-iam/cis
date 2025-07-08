resource "auth0_resource_server" "prod_sso_api" {
  identifier = "api.sso.mozilla.com"
  name       = "https://api.sso.mozilla.com"
}
