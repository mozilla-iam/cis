import boto3
import json
import logging
import os
import mock
import random
import subprocess
from boto3.dynamodb.conditions import Key
from cis_profile import FakeUser
from cis_profile import User
from cis_profile.fake_profile import FakeProfileConfig
from tests.fake_auth0 import FakeBearer
from tests.fake_auth0 import json_form_of_pk


logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")

logging.getLogger("boto").setLevel(logging.CRITICAL)
logging.getLogger("boto3").setLevel(logging.CRITICAL)
logging.getLogger("botocore").setLevel(logging.CRITICAL)


logger = logging.getLogger(__name__)


class TestProfile(object):
    def setup(self):
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["CIS_ENVIRONMENT"] = "local"
        name = "local-identity-vault"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        self.dynalite_port = str(random.randint(32000, 34000))
        os.environ["CIS_DYNALITE_PORT"] = self.dynalite_port
        self.dynaliteprocess = subprocess.Popen(["dynalite", "--port", self.dynalite_port], preexec_fn=os.setsid)
        conn = boto3.client(
            "dynamodb",
            region_name="us-west-2",
            aws_access_key_id="ak",
            aws_secret_access_key="sk",
            endpoint_url="http://localhost:{}".format(self.dynalite_port),
        )

        # XXX TBD this will eventually be replaced by logic from the vault module
        # The vault module will have the authoritative definitions for Attributes and GSI
        try:
            conn.create_table(
                TableName=name,
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[
                    {"AttributeName": "id", "AttributeType": "S"},
                    {"AttributeName": "user_uuid", "AttributeType": "S"},
                    {"AttributeName": "sequence_number", "AttributeType": "S"},
                    {"AttributeName": "primary_email", "AttributeType": "S"},
                    {"AttributeName": "primary_username", "AttributeType": "S"},
                ],
                ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "{}-sequence_number".format(name),
                        "KeySchema": [{"AttributeName": "sequence_number", "KeyType": "HASH"}],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                    },
                    {
                        "IndexName": "{}-primary_email".format(name),
                        "KeySchema": [{"AttributeName": "primary_email", "KeyType": "HASH"}],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                    },
                    {
                        "IndexName": "{}-primary_username".format(name),
                        "KeySchema": [{"AttributeName": "primary_username", "KeyType": "HASH"}],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                    },
                    {
                        "IndexName": "{}-user_uuid".format(name),
                        "KeySchema": [{"AttributeName": "user_uuid", "KeyType": "HASH"}],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                    },
                ],
            )
            waiter = conn.get_waiter("table_exists")
            waiter.wait(TableName="local-identity-vault", WaiterConfig={"Delay": 5, "MaxAttempts": 5})
        except Exception as e:
            logger.error("Table error: {}".format(e))
        user_profile = FakeUser(config=FakeProfileConfig().minimal())
        self.user_profile = user_profile.as_json()
        self.user_profile_dict = user_profile.as_dict()

    @mock.patch("cis_change_service.idp.get_jwks")
    def test_post_a_profile_and_retreiving_status_it_should_succeed(self, fake_jwks):
        os.environ["CIS_ENVIRONMENT"] = "local"
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        os.environ["CIS_DYNALITE_PORT"] = self.dynalite_port
        from cis_change_service import api

        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk
        token = f.generate_bearer_without_scope()
        api.app.testing = True
        self.app = api.app.test_client()
        result = self.app.post(
            "/v2/user",
            headers={"Authorization": "Bearer " + token},
            data=json.dumps(self.user_profile),
            content_type="application/json",
            follow_redirects=True,
        )

        response = json.loads(result.get_data())

        logger.info(response)

        dynamodb = boto3.resource(
            "dynamodb",
            region_name="us-west-2",
            aws_access_key_id="ak",
            aws_secret_access_key="sk",
            endpoint_url="http://localhost:{}".format(self.dynalite_port),
        )

        table = dynamodb.Table("local-identity-vault")
        resp = table.query(KeyConditionExpression=Key("id").eq(json.loads(self.user_profile)["user_id"]["value"]))
        user_from_vault = json.loads(resp["Items"][0]["profile"])
        assert user_from_vault["last_modified"]["value"] is not None
        assert user_from_vault["last_modified"]["signature"]["publisher"]["value"] is not None
        assert response is not None

    @mock.patch("cis_change_service.idp.get_jwks")
    def test_post_profiles_and_retrieving_status_it_should_succeed(self, fake_jwks):
        os.environ["CIS_ENVIRONMENT"] = "local"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["CIS_DYNALITE_PORT"] = self.dynalite_port
        from cis_change_service import api

        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk
        profiles = []
        for x in range(0, 10):
            profiles.append(FakeUser().as_json())
        token = f.generate_bearer_without_scope()
        api.app.testing = True
        self.app = api.app.test_client()
        result = self.app.post(
            "/v2/users",
            headers={"Authorization": "Bearer " + token},
            data=json.dumps(profiles),
            content_type="application/json",
            follow_redirects=True,
        )

        results = json.loads(result.get_data())
        assert results is not None

    @mock.patch("cis_change_service.idp.get_jwks")
    def test_post_profiles_and_update_it_and_retrieving_status_it_should_succeed(self, fake_jwks):
        os.environ["CIS_ENVIRONMENT"] = "local"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["CIS_DYNALITE_PORT"] = self.dynalite_port
        from cis_change_service import api

        # Post a new user
        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk
        token = f.generate_bearer_without_scope()
        api.app.testing = True
        self.app = api.app.test_client()
        my_fake_user = User(user_id="userA")
        my_fake_user.active.value = True
        my_fake_user.primary_email.value = "userA@example.net"
        my_fake_user.uuid.value = None
        my_fake_user.primary_username.value = None
        result = self.app.post(
            "/v2/user?user_id={}".format(my_fake_user.user_id.value),
            headers={"Authorization": "Bearer " + token},
            json=my_fake_user.as_dict(),
            content_type="application/json",
            follow_redirects=True,
        )
        results = json.loads(result.get_data())
        print("user posted", results)
        # Post it again
        result = self.app.post(
            "/v2/user?user_id={}".format(my_fake_user.user_id.value),
            headers={"Authorization": "Bearer " + token},
            json=my_fake_user.as_dict(),
            content_type="application/json",
            follow_redirects=True,
        )
        results = json.loads(result.get_data())
        print("result", results)
        assert results is not None
        assert results.get("description") == "No operation occurred: {'creates': None, 'updates': None, 'status': 202}"

    @mock.patch("cis_change_service.idp.get_jwks")
    def test_post_new_profile_with_primary_username_should_fail(self, fake_jwks):
        os.environ["CIS_ENVIRONMENT"] = "local"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis-verify.ini"
        os.environ["CIS_STREAM_BYPASS"] = "true"
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["CIS_DYNALITE_PORT"] = self.dynalite_port
        from cis_change_service import api

        f = FakeBearer()
        user_profile = FakeUser(config=FakeProfileConfig().minimal())
        user_profile.primary_username.value = "something"
        fake_jwks.return_value = json_form_of_pk
        token = f.generate_bearer_without_scope()
        api.app.testing = True
        self.app = api.app.test_client()
        result = self.app.post(
            "/v2/user",
            headers={"Authorization": "Bearer " + token},
            data=json.dumps(user_profile.as_dict()),
            content_type="application/json",
            follow_redirects=True,
        )

        results = json.loads(result.get_data())
        expected_result = {
            "code": "uuid_or_primary_username_set",
            "description": "The fields primary_username or uuid have been set in a new profile.",
        }

        assert result.status_code == 403
        assert results == expected_result

    @mock.patch("cis_change_service.idp.get_jwks")
    def test_post_new_profile_with_uuid_should_fail(self, fake_jwks):
        os.environ["CIS_ENVIRONMENT"] = "local"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis-verify.ini"
        os.environ["CIS_STREAM_BYPASS"] = "true"
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["CIS_DYNALITE_PORT"] = self.dynalite_port
        from cis_change_service import api

        f = FakeBearer()
        user_profile = FakeUser(config=FakeProfileConfig().minimal())
        user_profile.uuid.value = "something"
        fake_jwks.return_value = json_form_of_pk
        token = f.generate_bearer_without_scope()
        api.app.testing = True
        self.app = api.app.test_client()
        result = self.app.post(
            "/v2/user",
            headers={"Authorization": "Bearer " + token},
            data=json.dumps(user_profile.as_dict()),
            content_type="application/json",
            follow_redirects=True,
        )

        results = json.loads(result.get_data())
        expected_result = {
            "code": "uuid_or_primary_username_set",
            "description": "The fields primary_username or uuid have been set in a new profile.",
        }

        assert result.status_code == 403
        assert results == expected_result

    @mock.patch("cis_change_service.idp.get_jwks")
    def test_post_profiles_it_should_fail(self, fake_jwks):
        os.environ["CIS_ENVIRONMENT"] = "local"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis-verify.ini"
        os.environ["CIS_STREAM_BYPASS"] = "true"
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["CIS_DYNALITE_PORT"] = self.dynalite_port
        from cis_change_service import api

        f = FakeBearer()
        user_profile = FakeUser(config=FakeProfileConfig().minimal())
        user_profile.first_name.signature.publisher.name = "cis"
        user_profile.first_name.value = "Something"
        fake_jwks.return_value = json_form_of_pk
        token = f.generate_bearer_without_scope()
        api.app.testing = True
        self.app = api.app.test_client()
        result = self.app.post(
            "/v2/user",
            headers={"Authorization": "Bearer " + token},
            data=json.dumps(user_profile.as_dict()),
            content_type="application/json",
            follow_redirects=True,
        )

        results = json.loads(result.get_data())
        expected_result = {
            "code": "invalid_publisher",
            "description": "[create] cis is NOT allowed to publish field first_name",
        }

        assert result.status_code == 403
        assert results == expected_result

    @mock.patch("cis_change_service.idp.get_jwks")
    def test_delete_profile(self, fake_jwks):
        os.environ["CIS_ENVIRONMENT"] = "local"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["CIS_DYNALITE_PORT"] = self.dynalite_port
        from cis_change_service import api

        f = FakeBearer()
        fake_jwks.return_value = json_form_of_pk
        token = f.generate_bearer_without_scope()
        api.app.testing = True
        self.app = api.app.test_client()
        result = self.app.delete(
            "/v2/user?user_id={}".format(json.loads(self.user_profile)["user_id"]["value"]),
            headers={"Authorization": "Bearer " + token},
            data=json.dumps(self.user_profile),
            content_type="application/json",
            follow_redirects=True,
        )

        results = json.loads(result.get_data())
        assert results is not None
        assert result.status_code == 200

    def test_rewrite(self):
        from cis_change_service import profile

        os.environ["AWS_XRAY_SDK_ENABLED"] = "false"
        os.environ["CIS_ENVIRONMENT"] = "local"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis-verify.ini"

        v = profile.Vault()
        u = FakeUser()
        u.active.value = False
        u.active.signature.publisher.name = "ldap"
        u.sign_attribute("active", "ldap")
        ud = v._update_attr_owned_by_cis(u.user_id.value, u)
        assert ud.active.signature.publisher.name == "cis"

    def teardown(self):
        os.killpg(os.getpgid(self.dynaliteprocess.pid), 15)
