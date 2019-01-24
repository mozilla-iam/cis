import boto3
import json
import logging
import mock
import os
import random
import subprocess
from botocore.stub import Stubber
from cis_profile import FakeUser
from datetime import datetime
from datetime import timedelta
from tests.fake_auth0 import FakeBearer
from tests.fake_auth0 import json_form_of_pk


logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")

logging.getLogger("boto").setLevel(logging.CRITICAL)
logging.getLogger("boto3").setLevel(logging.CRITICAL)
logging.getLogger("botocore").setLevel(logging.CRITICAL)


logger = logging.getLogger(__name__)


class TestAPI(object):
    def setup(self):
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        from cis_change_service.common import get_config

        config = get_config()
        os.environ["CIS_DYNALITE_PORT"] = str(random.randint(32000, 34000))
        os.environ["CIS_KINESALITE_PORT"] = str(random.randint(32000, 34000))
        self.kinesalite_port = config("kinesalite_port", namespace="cis")
        self.kinesalite_host = config("kinesalite_host", namespace="cis")
        self.dynalite_port = config("dynalite_port", namespace="cis")
        self.dynaliteprocess = subprocess.Popen(["dynalite", "--port", self.dynalite_port], preexec_fn=os.setsid)
        self.kinesaliteprocess = subprocess.Popen(["kinesalite", "--port", self.kinesalite_port], preexec_fn=os.setsid)

        conn = Stubber(boto3.session.Session(region_name="us-west-2")).client.client(
            "kinesis", endpoint_url="http://{}:{}".format(self.kinesalite_host, self.kinesalite_port)
        )

        try:
            name = "local-stream"
            conn.create_stream(StreamName=name, ShardCount=1)
        except Exception as e:
            logger.error("Stream error: {}".format(e))
            # This just means we tried too many tests too fast.
            pass

        waiter = conn.get_waiter("stream_exists")

        waiter.wait(StreamName=name, Limit=100, WaiterConfig={"Delay": 1, "MaxAttempts": 5})

        tags_1 = {"Key": "cis_environment", "Value": "local"}
        tags_2 = {"Key": "application", "Value": "change-stream"}
        conn.add_tags_to_stream(StreamName=name, Tags=tags_1)
        conn.add_tags_to_stream(StreamName=name, Tags=tags_2)

        name = "local-identity-vault"
        conn = boto3.client(
            "dynamodb",
            region_name="us-west-2",
            aws_access_key_id="ak",
            aws_secret_access_key="sk",
            endpoint_url="http://localhost:{}".format(self.dynalite_port),
        )
        try:
            conn.create_table(
                TableName=name,
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[
                    {"AttributeName": "id", "AttributeType": "S"},
                    {"AttributeName": "uuid", "AttributeType": "S"},
                    {"AttributeName": "sequence_number", "AttributeType": "S"},
                    {"AttributeName": "primary_email", "AttributeType": "S"},
                    {"AttributeName": "primary_username", "AttributeType": "S"},
                    {"AttributeName": "profile", "AttributeType": "S"},
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
                        "IndexName": "{}-uuid".format(name),
                        "KeySchema": [{"AttributeName": "uuid", "KeyType": "HASH"}],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                    },
                ],
            )
            waiter = conn.get_waiter("table_exists")
            waiter.wait(TableName="local-identity-vault", WaiterConfig={"Delay": 1, "MaxAttempts": 5})
        except Exception as e:
            logger.error("Table error: {}".format(e))

        self.user_profile = FakeUser().as_json()
        from cis_change_service import api

        api.app.testing = True
        self.app = api.app.test_client()

    def test_index_exists(self):
        result = self.app.get("/v2/", follow_redirects=True)
        assert result.status_code == 200

    @mock.patch("cis_change_service.idp.get_jwks")
    def test_change_endpoint_returns(self, fake_jwks):
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

        json.loads(result.get_data())
        assert result.status_code == 200

    @mock.patch("cis_change_service.idp.get_jwks")
    def test_change_endpoint_fails_with_invalid_token(self, fake_jwks):
        from cis_change_service import api

        f = FakeBearer()
        bad_claims = {
            "iss": "https://auth-dev.mozilla.auth0.com/",
            "sub": "mc1l0G4sJI2eQfdWxqgVNcRAD9EAgHib@clients",
            "aud": "https://hacks",
            "iat": (datetime.utcnow() - timedelta(seconds=3100)).strftime("%s"),
            "exp": (datetime.utcnow() - timedelta(seconds=3100)).strftime("%s"),
            "scope": "read:allthething",
            "gty": "client-credentials",
        }

        fake_jwks.return_value = json_form_of_pk
        token = f.generate_bearer_with_scope("read:profile", bad_claims)
        api.app.testing = True
        self.app = api.app.test_client()
        result = self.app.get("/v2/user", headers={"Authorization": "Bearer " + token}, follow_redirects=True)

        assert result.status_code == 401

    @mock.patch("cis_change_service.idp.get_jwks")
    def test_stream_bypass_publishing_mode_it_should_succeed(self, fake_jwks):
        from cis_change_service import api

        os.environ["CIS_STREAM_BYPASS"] = "true"
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

        json.loads(result.get_data())
        assert result.status_code == 200

    @mock.patch("cis_change_service.idp.get_jwks")
    def test_change_endpoint_fails_with_invalid_token_and_jwt_validation_false(self, fake_jwks):
        from cis_change_service import api

        os.environ["CIS_JWT_VALIDATION"] = "false"
        f = FakeBearer()
        bad_claims = {
            "iss": "https://auth-dev.mozilla.auth0.com/",
            "sub": "mc1l0G4sJI2eQfdWxqgVNcRAD9EAgHib@clients",
            "aud": "https://hacks",
            "iat": (datetime.utcnow() - timedelta(seconds=3100)).strftime("%s"),
            "exp": (datetime.utcnow() - timedelta(seconds=3100)).strftime("%s"),
            "scope": "read:allthething",
            "gty": "client-credentials",
        }

        fake_jwks.return_value = json_form_of_pk
        token = f.generate_bearer_with_scope("read:profile", bad_claims)
        api.app.testing = True
        self.app = api.app.test_client()
        result = self.app.get(
            "/v2/user",
            headers={"Authorization": "Bearer " + token},
            data=json.dumps(self.user_profile),
            content_type="application/json",
            follow_redirects=True,
        )

        assert result.status_code == 200

    def teardown(self):
        os.killpg(os.getpgid(self.dynaliteprocess.pid), 15)
        os.killpg(os.getpgid(self.kinesaliteprocess.pid), 15)
