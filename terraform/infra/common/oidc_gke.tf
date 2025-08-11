# From:
# https://github.com/mozilla/global-platform-admin/blob/d3ba91536f92d2de15c9fc0f22a216f0d6cadc59/platform-shared/k8s/bootstrap/webservices-high-private-nonprod-us-west1.yaml
module "oidc_gke_webservices_high_private_nonprod" {
  source           = "github.com/mozilla/terraform-modules//aws_gke_oidc_config?ref=aws_gke_oidc_config-0.1.0"
  gcp_region       = "us-west1"
  gcp_project_id   = "moz-fx-webservices-high-nonpro"
  gke_cluster_name = "webservices-high-nonprod"
}

# From:
# https://github.com/mozilla/global-platform-admin/blob/d3ba91536f92d2de15c9fc0f22a216f0d6cadc59/platform-shared/k8s/bootstrap/webservices-high-private-prod-us-west1.yaml
module "oidc_gke_webservices_high_private_prod" {
  source           = "github.com/mozilla/terraform-modules//aws_gke_oidc_config?ref=aws_gke_oidc_config-0.1.0"
  gcp_region       = "us-west1"
  gcp_project_id   = "moz-fx-webservices-high-prod"
  gke_cluster_name = "webservices-high-prod"
}
