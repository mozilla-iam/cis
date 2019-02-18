import boto3
import json
import jsonschema
import logging
import http.client
import os
from . import helpers
from cis_aws import connect
from cis_profile import fake_profile
from cis_profile import profile
from cis_profile import WellKnown
from cis_identity_vault.models import user


logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("botocore").setLevel(logging.CRITICAL)


class TestPersonApi(object):
    def setup(self):
        cis_environment = os.getenv("CIS_ENVIRONMENT", "development")
        os.environ["CIS_ENVIRONMENT"] = cis_environment
        os.environ["CIS_ASSUME_ROLE_ARN"] = "None"
        self.connection_object = connect.AWS()
        self.connection_object._boto_session = boto3.session.Session(region_name="us-west-2")
        self.idv = self.connection_object.identity_vault_client()
        logger.info("Generating a single fake user.")
        u = fake_profile.FakeUser()
        u = helpers.ensure_appropriate_publishers_and_sign(fake_profile=u, condition="create")
        u.verify_all_publishers(profile.User(user_structure_json=None))
        self.durable_profile = u.as_json()
        self.durable_profiles = []

        logger.info("Generating 10 fake users.")
        for x in range(0, 10):
            u = fake_profile.FakeUser()
            u = helpers.ensure_appropriate_publishers_and_sign(fake_profile=u, condition="create")
            self.durable_profiles.append(u.as_json())

        logger.info("Bypassing change service and writing directly to the id_vault.")
        vault = user.Profile(
            dynamodb_table_resource=self.idv["table"], dyanamodb_client=self.idv["client"], transactions=True
        )

        res = vault.create(user_profile=self.durable_profile)
        logger.info("Single user created in vault result: {}".format(res))

    def exchange_for_access_token(self):
        conn = http.client.HTTPSConnection("auth.mozilla.auth0.com")
        payload_dict = dict(
            client_id=helpers.get_client_id(),
            client_secret=helpers.get_client_secret(),
            audience=helpers.get_url_dict().get("audience"),
            grant_type="client_credentials",
            scopes="read:fullprofile",
        )

        payload = json.dumps(payload_dict)
        headers = {"content-type": "application/json"}
        conn.request("POST", "/oauth/token", payload, headers)
        res = conn.getresponse()
        data = json.loads(res.read())
        return data["access_token"]

    def test_paginated_users():
        access_token = exchange_for_access_token()
        conn = http.client.HTTPSConnection(base_url)
        headers = {"authorization": "Bearer {}".format(access_token)}
        conn.request("GET", "/v2/users", headers=headers)
        res = conn.getresponse()
        data = json.loads(res.read())
        return data

    def test_get_single_user():
        access_token = exchange_for_access_token()
        conn = http.client.HTTPSConnection(base_url)
        headers = {"authorization": "Bearer {}".format(access_token)}
        conn.request("GET", "/v2/user/primary_email/jeffreygreen%40gmail.com", headers=headers)
        res = conn.getresponse()
        data = json.loads(res.read())
        return data
