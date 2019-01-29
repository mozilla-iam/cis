import boto3
import json
import logging
import os
from cis_identity_vault import vault
from mock import patch
from moto import mock_dynamodb2
from moto import mock_sts
from tests.fake_auth0 import FakeBearer
from tests.fake_auth0 import json_form_of_pk


logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")

logging.getLogger("boto").setLevel(logging.CRITICAL)
logging.getLogger("boto3").setLevel(logging.CRITICAL)
logging.getLogger("botocore").setLevel(logging.CRITICAL)


logger = logging.getLogger(__name__)

indexed_fields = ["user_id", "uuid", "primary_email", "primary_username"]


@mock_dynamodb2
@mock_sts
class TestAPI(object):
    def setup_class(self):
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        from cis_profile_retrieval_service.common import seed

        vault_client = vault.IdentityVault()
        vault_client.boto_session = boto3.session.Session(region_name="us-west-2")
        vault_client.connect()
        vault_client.create()
        vault_client.find_or_create()

        self.dynamodb_client = boto3.client(
            "dynamodb", region_name="us-west-2", aws_access_key_id="ak", aws_secret_access_key="sk"
        )

        self.dynamodb_resource = boto3.resource(
            "dynamodb", region_name="us-west-2", aws_access_key_id="ak", aws_secret_access_key="sk"
        )
        seed(number_of_fake_users=100)
        self.table = self.dynamodb_resource.Table("blue-identity-vault")
        from cis_profile_retrieval_service import v2_api as api

        api.app.testing = True
        self.app = api.app.test_client()

    def test_that_we_seeded_the_table(self):
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        from cis_identity_vault.models import user

        profile = user.Profile(self.table)
        profiles = profile.all
        assert len(profiles) >= 54

    @patch("cis_profile_retrieval_service.idp.get_jwks")
    def test_profiles_returns_a_list(self, fake_jwks):
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk
        token = f.generate_bearer_with_scope("read:fullprofile display:all")

        result = self.app.get("/v2/users", headers={"Authorization": "Bearer " + token}, follow_redirects=True)

        assert result.json is not None
        assert len(result.json["Items"]) == 25
        assert result.json["nextPage"] is not None
        assert result.json["nextPage"] != ""

        next_page = result.json["nextPage"]
        # Follow the paginator
        paged_query = self.app.get(
            "/v2/users?nextPage={}".format(json.dumps(next_page)),
            headers={"Authorization": "Bearer " + token},
            follow_redirects=True,
        )

        assert len(paged_query.json["Items"]) == 25
        assert paged_query.json["nextPage"] is not None
        assert paged_query.json["nextPage"] != ""
        assert paged_query.json["Items"] != result.json["Items"]

        sample_primary_email = result.json["Items"][0]["primary_email"]["value"]
        primary_email_query = self.app.get(
            "/v2/users?primaryEmail={}".format(sample_primary_email),
            headers={"Authorization": "Bearer " + token},
            follow_redirects=True,
        )

        assert len(primary_email_query.json["Items"]) == 1

        token = f.generate_bearer_with_scope("read:profile display:all")
        public_data_class_query = self.app.get(
            "/v2/users", headers={"Authorization": "Bearer " + token}, follow_redirects=True
        )

        for profile in public_data_class_query.json["Items"]:
            assert profile.get("access_information").get("hris") is None

        token = f.generate_bearer_with_scope("read:profile display:all")
        single_user_public_data_class_query = self.app.get(
            "/v2/user/user_id/{}".format(result.json["Items"][0]["user_id"]["value"]),
            headers={"Authorization": "Bearer " + token},
            follow_redirects=True,
        )

        assert single_user_public_data_class_query.json.get("access_information").get("hris") is None

        token = f.generate_bearer_with_scope("read:fullprofile display:all")
        single_user_all_data_class_query = self.app.get(
            "/v2/user/user_id/{}".format(result.json["Items"][0]["user_id"]["value"]),
            headers={"Authorization": "Bearer " + token},
            follow_redirects=True,
        )

        assert single_user_all_data_class_query.json.get("access_information")

    @patch("cis_profile_retrieval_service.idp.get_jwks")
    def test_users_with_all(self, fake_jwks):
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk

        # data classification: ALL, display scope: ALL
        token = f.generate_bearer_with_scope("read:fullprofile display:all")
        query = self.app.get("/v2/users", headers={"Authorization": "Bearer " + token}, follow_redirects=True)

        for profile in query.json["Items"]:
            assert profile.get("access_information").get("access_provider") is not None
            assert profile.get("staff_information").get("cost_center") is not None
            assert profile.get("uuid") is not None

    @patch("cis_profile_retrieval_service.idp.get_jwks")
    def test_users_with_dispaly_level_params_and_scopes(self, fake_jwks):
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk

        # data classification: ALL, display scope: PUBLIC
        token = f.generate_bearer_with_scope("read:fullprofile display:public")
        query = self.app.get("/v2/users", headers={"Authorization": "Bearer " + token}, follow_redirects=True)

        for profile in query.json["Items"]:
            assert profile.get("access_information").get("access_provider") is None
            assert profile.get("staff_information").get("cost_center") is None
            assert profile.get("uuid") is not None

        # data classification: ALL, display scope: STAFF
        token = f.generate_bearer_with_scope("read:fullprofile display:staff")
        query = self.app.get("/v2/users", headers={"Authorization": "Bearer " + token}, follow_redirects=True)

        for profile in query.json["Items"]:
            assert profile.get("access_information").get("access_provider") is None
            assert profile.get("staff_information").get("cost_center") is not None
            assert profile.get("uuid") is not None

    @patch("cis_profile_retrieval_service.idp.get_jwks")
    def test_users_with_scopes(self, fake_jwks):
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk

        # data classification: PUBLIC, display scope: ALL
        token = f.generate_bearer_with_scope("display:all")
        query = self.app.get("/v2/users", headers={"Authorization": "Bearer " + token}, follow_redirects=True)

        for profile in query.json["Items"]:
            assert profile.get("access_information").get("access_provider") is None
            assert profile.get("staff_information").get("cost_center") is None
            assert profile.get("uuid") is not None

        # data classification: STAFF, display scope: ALL
        token = f.generate_bearer_with_scope("classification:workgroup:staff_only display:all")
        query = self.app.get("/v2/users", headers={"Authorization": "Bearer " + token}, follow_redirects=True)

        for profile in query.json["Items"]:
            assert profile.get("access_information").get("access_provider") is None
            assert profile.get("staff_information").get("cost_center") is not None
            assert profile.get("staff_information").get("title") is None
            assert profile.get("uuid") is not None

        # data classification: STAFF + MOZILLA_CONFIDENTIAL, display scope: ALL
        token = f.generate_bearer_with_scope(
            "classification:workgroup:staff_only classification:mozilla_confidential display:all"
        )
        query = self.app.get("/v2/users", headers={"Authorization": "Bearer " + token}, follow_redirects=True)

        for profile in query.json["Items"]:
            assert profile.get("access_information").get("access_provider") is None
            assert profile.get("staff_information").get("cost_center") is not None
            assert profile.get("staff_information").get("title") is not None
            assert profile.get("uuid") is not None

    @patch("cis_profile_retrieval_service.idp.get_jwks")
    def test_find_by_x(self, fake_jwks):
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk

        token = f.generate_bearer_with_scope("read:fullprofile display:all")

        result = self.app.get("/v2/users", headers={"Authorization": "Bearer " + token}, follow_redirects=True)

        profile = result.json["Items"][0]
        for field in indexed_fields:

            # data classification: ALL, display scope: ALL, display parameter: -
            token = f.generate_bearer_with_scope("read:fullprofile display:all")
            query = self.app.get(
                "/v2/user/{}/{}".format(field, profile[field]["value"]),
                headers={"Authorization": "Bearer " + token},
                follow_redirects=True,
            )

            assert query.json.get("access_information").get("access_provider") is not None
            assert query.json.get("staff_information").get("cost_center") is not None
            assert query.json.get("uuid") is not None

    @patch("cis_profile_retrieval_service.idp.get_jwks")
    def test_find_by_x_with_data_classification_scopes(self, fake_jwks):
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk

        token = f.generate_bearer_with_scope("read:fullprofile display:all")

        result = self.app.get("/v2/users", headers={"Authorization": "Bearer " + token}, follow_redirects=True)

        profile = result.json["Items"][0]
        for field in indexed_fields:

            # data classification: PUBLIC, display scope: ALL, display parameter: -
            token = f.generate_bearer_with_scope("display:all")
            query = self.app.get(
                "/v2/user/{}/{}".format(field, profile[field]["value"]),
                headers={"Authorization": "Bearer " + token},
                follow_redirects=True,
            )

            assert query.json.get("access_information").get("access_provider") is None
            assert query.json.get("staff_information").get("cost_center") is None
            assert query.json.get("uuid") is not None

            # data classification: STAFF, display scope: ALL, display parameter: -
            token = f.generate_bearer_with_scope("classification:workgroup:staff_only display:all")
            query = self.app.get(
                "/v2/user/{}/{}".format(field, profile[field]["value"]),
                headers={"Authorization": "Bearer " + token},
                follow_redirects=True,
            )

            assert query.json.get("access_information").get("access_provider") is None
            assert query.json.get("staff_information").get("cost_center") is not None
            assert query.json.get("uuid") is not None

            # data classification: STAFF, display scope: PUBLIC, display parameter: -
            token = f.generate_bearer_with_scope("classification:workgroup:staff_only display:public")
            query = self.app.get(
                "/v2/user/{}/{}".format(field, profile[field]["value"]),
                headers={"Authorization": "Bearer " + token},
                follow_redirects=True,
            )

            assert not query.json.get("access_information").get("access_provider")
            assert not query.json.get("staff_information").get("cost_center")
            assert query.json.get("uuid")

    @patch("cis_profile_retrieval_service.idp.get_jwks")
    def test_find_by_x_with_dispaly_level_params_and_scopes(self, fake_jwks):
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk

        token = f.generate_bearer_with_scope("read:fullprofile display:all")

        result = self.app.get("/v2/users", headers={"Authorization": "Bearer " + token}, follow_redirects=True)

        profile = result.json["Items"][0]
        for field in indexed_fields:

            # data classification: ALL, display scope: PUBLIC, display parameter: -
            token = f.generate_bearer_with_scope("read:fullprofile display:public")
            query = self.app.get(
                "/v2/user/{}/{}".format(field, profile[field]["value"]),
                headers={"Authorization": "Bearer " + token},
                follow_redirects=True,
            )

            assert query.json.get("access_information").get("access_provider") is None
            assert query.json.get("staff_information").get("cost_center") is None
            assert query.json.get("uuid") is not None

            # data classification: ALL, display scope: STAFF, display parameter: -
            token = f.generate_bearer_with_scope("read:fullprofile display:staff")
            query = self.app.get(
                "/v2/user/{}/{}".format(field, profile[field]["value"]),
                headers={"Authorization": "Bearer " + token},
                follow_redirects=True,
            )

            assert query.json.get("access_information").get("access_provider") is None
            assert query.json.get("staff_information").get("cost_center") is not None
            assert query.json.get("uuid") is not None

            # data classification: ALL, display scope: STAFF, display parameter: PUBLIC
            token = f.generate_bearer_with_scope("read:fullprofile display:staff")
            query = self.app.get(
                "/v2/user/{}/{}?filterDisplay=public".format(field, profile[field]["value"]),
                headers={"Authorization": "Bearer " + token},
                follow_redirects=True,
            )

            assert not query.json.get("access_information").get("access_provider")
            assert not query.json.get("staff_information").get("cost_center")
            assert query.json.get("uuid")

            # data classification: ALL, display scope: PUBLIC, display parameter: STAFF
            token = f.generate_bearer_with_scope("read:fullprofile display:public")
            query = self.app.get(
                "/v2/user/{}/{}?filterDisplay=staff".format(field, profile[field]["value"]),
                headers={"Authorization": "Bearer " + token},
                follow_redirects=True,
            )

            assert not query.json.get("access_information").get("access_provider")
            assert not query.json.get("staff_information").get("cost_center")
            assert query.json.get("uuid")
