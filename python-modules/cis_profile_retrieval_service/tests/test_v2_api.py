import boto3
import json
import logging
import os
import random
import subprocess
from cis_identity_vault import vault
from mock import patch
from tests.fake_auth0 import FakeBearer
from tests.fake_auth0 import json_form_of_pk


logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")

logging.getLogger("boto").setLevel(logging.CRITICAL)
logging.getLogger("boto3").setLevel(logging.CRITICAL)
logging.getLogger("botocore").setLevel(logging.CRITICAL)


logger = logging.getLogger(__name__)

indexed_fields = ["user_id", "uuid", "primary_email", "primary_username"]


class TestAPI(object):
    def setup_class(self):
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        self.dynalite_port = str(random.randint(32000, 34000))
        os.environ["CIS_DYNALITE_PORT"] = self.dynalite_port
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["AWS_ACCESS_KEY_ID"] = "foo"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "foo"
        self.dynalite_host = "localhost"
        self.dynaliteprocess = subprocess.Popen(
            [
                "/usr/sbin/java",
                "-Djava.library.path=/opt/dynamodb_local/DynamoDBLocal_lib",
                "-jar",
                "/opt/dynamodb_local/DynamoDBLocal.jar",
                "-inMemory",
                "-port",
                self.dynalite_port,
            ],
            preexec_fn=os.setsid,
        )
        from cis_profile_retrieval_service.common import seed

        vault_client = vault.IdentityVault()
        vault_client.boto_session = boto3.session.Session(region_name="us-west-2")
        vault_client.connect()
        vault_client.create()
        vault_client.find_or_create()

        self.dynamodb_client = boto3.client(
            "dynamodb",
            region_name="us-west-2",
            aws_access_key_id="ak",
            aws_secret_access_key="sk",
            endpoint_url="http://{}:{}".format(self.dynalite_host, self.dynalite_port),
        )

        self.dynamodb_resource = boto3.resource(
            "dynamodb",
            region_name="us-west-2",
            aws_access_key_id="ak",
            aws_secret_access_key="sk",
            endpoint_url="http://{}:{}".format(self.dynalite_host, self.dynalite_port),
        )
        seed(number_of_fake_users=55)
        self.table = self.dynamodb_resource.Table("local-identity-vault")
        from cis_profile_retrieval_service import v2_api as api

        api.app.testing = True
        self.app = api.app.test_client()

    @patch("cis_profile_retrieval_service.idp.get_jwks")
    def test_returning_query_by_any_staff_only_active_true(self, fake_jwks):
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk

        token = f.generate_bearer_with_scope("read:fullprofile display:all search:all")
        logger.info("Attempting to query all staff.")
        result = self.app.get(
            "/v2/users/id/all/by_attribute_contains?staff_information.staff=True&active=True",
            headers={"Authorization": "Bearer " + token},
            follow_redirects=True,
        )

        logger.info("All staff users returned.")
        assert result.json["users"] is not None

        if result.json["nextPage"]:
            next_page = result.json["nextPage"]
            result = self.app.get(
                f"/v2/users/id/all/by_attribute_contains?staff_information.staff=True&active=True&nextPage={next_page}",
                headers={"Authorization": "Bearer " + token},
                follow_redirects=True,
            )
            logger.info("An additional page of all staff users returned")
            assert result.json["users"] is not None

    @patch("cis_profile_retrieval_service.idp.get_jwks")
    def test_returning_query_by_any_staff_only_active_true_with_full_profiles(self, fake_jwks):
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk

        token = f.generate_bearer_with_scope("read:fullprofile display:all search:all")
        logger.info("Attempting to query all staff.")
        result = self.app.get(
            "/v2/users/id/all/by_attribute_contains?staff_information.staff=True&active=True&fullProfiles=True",
            headers={"Authorization": "Bearer " + token},
            follow_redirects=True,
        )

        logger.info("All staff users returned.")
        assert result.json["users"] is not None

        for user in result.json["users"]:
            assert user["profile"] is not None

        if result.json["nextPage"]:
            next_page = result.json["nextPage"]
            result = self.app.get(
                f"/v2/users/id/all/by_attribute_contains?staff_information.staff=\
                True&active=True&fullProfiles=True&nextPage={next_page}",
                headers={"Authorization": "Bearer " + token},
                follow_redirects=True,
            )
            logger.info("An additional page of all staff users returned")
            assert result.json["users"] is not None

    @patch("cis_profile_retrieval_service.idp.get_jwks")
    def test_returning_query_by_any_find_ldap_members(self, fake_jwks):
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk

        token = f.generate_bearer_with_scope("read:fullprofile display:all search:all")
        logger.info("Attempting to query all staff.")
        result = self.app.get(
            "/v2/users/id/all/by_attribute_contains?staff_information.staff=True&active=True&fullProfiles=True",
            headers={"Authorization": "Bearer " + token},
            follow_redirects=True,
        )

        logger.info("All staff users returned.")
        assert result.json["users"] is not None

        ldap_groups = {}

        # Go find a user with an ldap group
        for user in result.json["users"]:
            if user["profile"]["access_information"]["ldap"]["values"] != {}:
                ldap_groups = user["profile"]["access_information"]["ldap"]["values"]
                break
            else:
                continue

        for k in ldap_groups:
            logger.info("Attempting to query for: {}".format(k))
            result = self.app.get(
                f"/v2/users/id/all/by_attribute_contains?access_information.ldap={k}&active=True&fullProfiles=False",
                headers={"Authorization": "Bearer " + token},
                follow_redirects=True,
            )

            assert len(result.json["users"]) > 0

    @patch("cis_profile_retrieval_service.idp.get_jwks")
    def test_profiles_returns_a_list(self, fake_jwks):
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk
        token = f.generate_bearer_with_scope("read:fullprofile display:all")

        result = self.app.get("/v2/users", headers={"Authorization": "Bearer " + token}, follow_redirects=True)
        assert result.json is not None
        total_users_retrieved = len(result.json["Items"])
        assert total_users_retrieved > 20
        logger.info("Paginated query to all users returned: {}".format(len(result.json["Items"])))

        assert result.json["nextPage"] is not None
        assert result.json["nextPage"] != ""

        next_page = result.json["nextPage"]
        # Follow the paginator
        paged_query = self.app.get(
            "/v2/users?nextPage={}".format(json.dumps(next_page)),
            headers={"Authorization": "Bearer " + token},
            follow_redirects=True,
        )

        assert len(paged_query.json["Items"]) >= 1

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
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
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
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
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
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
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
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
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
            assert query.json.get("active").get("value") is True

    @patch("cis_profile_retrieval_service.idp.get_jwks")
    def test_metadata_by_primary_email(self, fake_jwks):
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk

        token = f.generate_bearer_with_scope("read:fullprofile display:all")

        result = self.app.get("/v2/users", headers={"Authorization": "Bearer " + token}, follow_redirects=True)

        query = self.app.get(
            "/v2/user/metadata/{}".format(result.json["Items"][0]["primary_email"]["value"]),
            follow_redirects=True,
        )

        assert query.json.get("exists").get("cis") is True
        assert query.json.get("exists").get("ldap") is True

    @patch("cis_profile_retrieval_service.idp.get_jwks")
    def test_find_by_x_active_true(self, fake_jwks):
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk

        token = f.generate_bearer_with_scope("read:fullprofile display:all")

        result = self.app.get(
            "/v2/users?active=true", headers={"Authorization": "Bearer " + token}, follow_redirects=True
        )

        profile = result.json["Items"][0]
        for field in indexed_fields:

            # data classification: ALL, display scope: ALL, display parameter: -
            token = f.generate_bearer_with_scope("read:fullprofile display:all")
            query = self.app.get(
                "/v2/user/{}/{}?active=true".format(field, profile[field]["value"]),
                headers={"Authorization": "Bearer " + token},
                follow_redirects=True,
            )

            assert query.json.get("access_information").get("access_provider") is not None
            assert query.json.get("staff_information").get("cost_center") is not None
            assert query.json.get("uuid") is not None
            assert query.json.get("active").get("value") is True

            query = self.app.get(
                "/v2/user/{}/{}?active=false".format(field, profile[field]["value"]),
                headers={"Authorization": "Bearer " + token},
                follow_redirects=True,
            )

            assert query.json == {}

    @patch("cis_profile_retrieval_service.idp.get_jwks")
    def test_find_by_x_active_false(self, fake_jwks):
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk

        token = f.generate_bearer_with_scope("read:fullprofile display:all")

        result = self.app.get(
            "/v2/users?active=false", headers={"Authorization": "Bearer " + token}, follow_redirects=True
        )
        next_page = result.json["nextPage"]

        while next_page and len(result.json["Items"]) == 0:
            result = self.app.get(
                "/v2/users?active=false&nextPage={}".format(json.dumps(next_page)),
                headers={"Authorization": "Bearer " + token},
                follow_redirects=True,
            )
            next_page = result.json["nextPage"]

        profile = result.json["Items"][0]
        for field in indexed_fields:

            # data classification: ALL, display scope: ALL, display parameter: -
            token = f.generate_bearer_with_scope("read:fullprofile display:all")
            query = self.app.get(
                "/v2/user/{}/{}?active=false".format(field, profile[field]["value"]),
                headers={"Authorization": "Bearer " + token},
                follow_redirects=True,
            )

            assert query.json.get("access_information").get("access_provider") is not None
            assert query.json.get("staff_information").get("cost_center") is not None
            assert query.json.get("uuid") is not None
            assert query.json.get("active").get("value") is False

            query = self.app.get(
                "/v2/user/{}/{}?active=true".format(field, profile[field]["value"]),
                headers={"Authorization": "Bearer " + token},
                follow_redirects=True,
            )

            assert query.json == {}

    @patch("cis_profile_retrieval_service.idp.get_jwks")
    def test_find_by_x_with_data_classification_scopes(self, fake_jwks):
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
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

            # data classification: public, display scope: trustedonly, display parameter: -
            token = f.generate_bearer_with_scope("classification:public display:all")
            query = self.app.get(
                "/v2/user/{}/{}".format(field, profile[field]["value"]),
                headers={"Authorization": "Bearer " + token},
                follow_redirects=True,
            )
            assert query.json["access_information"]["ldap"] is not None

    @patch("cis_profile_retrieval_service.idp.get_jwks")
    def test_find_by_x_with_dispaly_level_params_and_scopes(self, fake_jwks):
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
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

    @patch("cis_profile_retrieval_service.idp.get_jwks")
    def test_returning_all(self, fake_jwks):
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk

        token = f.generate_bearer_with_scope("read:fullprofile display:all")
        result = self.app.get(
            "/v2/users/id/all?connectionMethod=email",
            headers={"Authorization": "Bearer " + token},
            follow_redirects=True,
        )
        assert isinstance(result.json["users"], list)
        assert isinstance(result.json["users"][0], dict)
        assert len(result.json["users"]) > 0

    @patch("cis_profile_retrieval_service.idp.get_jwks")
    def test_returning_all_filter_on_active_false(self, fake_jwks):
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk

        token = f.generate_bearer_with_scope("read:fullprofile display:all")
        result = self.app.get(
            "/v2/users/id/all?connectionMethod=email&active=False",
            headers={"Authorization": "Bearer " + token},
            follow_redirects=True,
        )
        assert isinstance(result.json["users"], list)
        assert len(result.json["users"]) > 0
        assert len(result.json["users"]) == 1  # One disabled user is always created in the seed.

    @patch("cis_profile_retrieval_service.idp.get_jwks")
    def test_returning_all_filter_on_active_true(self, fake_jwks):
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk

        token = f.generate_bearer_with_scope("read:fullprofile display:all")
        result = self.app.get(
            "/v2/users/id/all?connectionMethod=email&active=True",
            headers={"Authorization": "Bearer " + token},
            follow_redirects=True,
        )
        assert isinstance(result.json["users"], list)
        assert isinstance(result.json["users"][0], dict)
        assert len(result.json["users"]) > 0

        while result.json["nextPage"] is not None:
            next_page = result.json["nextPage"]
            result = self.app.get(
                f"/v2/users/id/all?connectionMethod=email&active=True&nextPage={next_page}",
                headers={"Authorization": "Bearer " + token},
                follow_redirects=True,
            )
            assert result.json["users"] is not None
