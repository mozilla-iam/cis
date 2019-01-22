import boto3
import json
import logging
import os
import mock
import subprocess
from botocore.stub import Stubber
from cis_profile import FakeUser
from tests.fake_auth0 import FakeBearer
from tests.fake_auth0 import json_form_of_pk


logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")

logging.getLogger("boto").setLevel(logging.CRITICAL)
logging.getLogger("boto3").setLevel(logging.CRITICAL)
logging.getLogger("botocore").setLevel(logging.CRITICAL)


logger = logging.getLogger(__name__)


class TestProfile(object):
    def setup(self):
        from cis_change_service.common import get_config

        os.environ["CIS_ENVIRONMENT"] = "local"
        name = "local-identity-vault"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        config = get_config()
        kinesalite_port = config("kinesalite_port", namespace="cis")
        kinesalite_host = config("kinesalite_host", namespace="cis")
        dynalite_port = config("dynalite_port", namespace="cis")
        self.dynaliteprocess = subprocess.Popen(["dynalite", "--port", dynalite_port], preexec_fn=os.setsid)
        self.kinesaliteprocess = subprocess.Popen(["kinesalite", "--port", kinesalite_port], preexec_fn=os.setsid)
        conn = boto3.client(
            "dynamodb",
            region_name="us-west-2",
            aws_access_key_id="ak",
            aws_secret_access_key="sk",
            endpoint_url="http://localhost:{}".format(dynalite_port),
        )

        # XXX TBD this will eventually be replaced by logic from the vault module
        # The vault module will have the authoritative definitions for Attributes and GSI
        try:
            conn.create_table(
                TableName=name,
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[
                    {"AttributeName": "id", "AttributeType": "S"},
                    {"AttributeName": "uuid", "AttributeType": "S"},
                    {"AttributeName": "sequence_number", "AttributeType": "S"},
                    {"AttributeName": "primary_email", "AttributeType": "S"},
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
                        "IndexName": "{}-uuid".format(name),
                        "KeySchema": [{"AttributeName": "uuid", "KeyType": "HASH"}],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                    },
                ],
            )
        except Exception as e:
            logger.error("Table error: {}".format(e))

        conn = Stubber(boto3.session.Session(region_name="us-west-2")).client.client(
            "kinesis",
            endpoint_url="http://localhost:{}".format(kinesalite_port).format(kinesalite_host, kinesalite_port),
        )

        try:
            name = "local-stream"
            conn.create_stream(StreamName=name, ShardCount=1)
        except Exception as e:
            logger.error("Stream creation error: {}".format(e))
            # This just means we tried too many tests too fast.
            pass

        waiter = conn.get_waiter("stream_exists")

        waiter.wait(StreamName=name, Limit=100, WaiterConfig={"Delay": 1, "MaxAttempts": 5})

        tags_1 = {"Key": "cis_environment", "Value": "local"}
        tags_2 = {"Key": "application", "Value": "change-stream"}
        conn.add_tags_to_stream(StreamName=name, Tags=tags_1)
        conn.add_tags_to_stream(StreamName=name, Tags=tags_2)
        self.user_profile = FakeUser().as_json()

    @mock.patch("cis_change_service.idp.get_jwks")
    def test_post_a_profile_and_retreiving_status_it_should_succeed(self, fake_jwks):
        os.environ["CIS_ENVIRONMENT"] = "local"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
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
        assert response is not None

    @mock.patch("cis_change_service.idp.get_jwks")
    def test_post_profiles_and_retrieving_status_it_should_succeed(self, fake_jwks):
        os.environ["CIS_ENVIRONMENT"] = "local"
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
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

    def teardown(self):
        os.killpg(os.getpgid(self.dynaliteprocess.pid), 15)
        os.killpg(os.getpgid(self.kinesaliteprocess.pid), 15)
