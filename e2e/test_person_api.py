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
logging.getLogger("cis_crypto").setLevel(logging.CRITICAL)


class TestPersonApi(object):
    def setup(self):
        self.helper_configuration = helpers.Configuration()
        cis_environment = os.getenv("CIS_ENVIRONMENT", "development")
        os.environ["CIS_ENVIRONMENT"] = cis_environment
        os.environ["CIS_ASSUME_ROLE_ARN"] = "None"
        self.connection_object = connect.AWS()
        self.connection_object._boto_session = boto3.session.Session(region_name="us-west-2")
        self.idv = self.connection_object.identity_vault_client()
        # u = fake_profile.FakeUser()
        # u = helpers.ensure_appropriate_publishers_and_sign(fake_profile=u, condition="create")
        # u.verify_all_publishers(profile.User(user_structure_json=None))

        fh = open("fixtures/durable.json")
        self.durable_profile = fh.read()
        fh.close()

        self.durable_profiles = []

        logger.info("Loading 10 fake users.")
        for x in range(0, 10):
            fh = open("fixtures/{}.json".format(x))
            self.durable_profiles.append(fh.read())
            fh.close()

        logger.info("Bypassing change service and writing directly to the id_vault.")
        vault = user.Profile(
            dynamodb_table_resource=self.idv["table"], dynamodb_client=self.idv["client"], transactions=True
        )

        this_user = json.loads(self.durable_profile)
        user_profile = {
            "id": this_user["user_id"]["value"],
            "profile": self.durable_profile,
            "primary_username": this_user["primary_username"]["value"],
            "primary_email": this_user["primary_email"]["value"],
            "user_uuid": this_user["uuid"]["value"],
            "sequence_number": "1",
        }

        res = vault.find_or_create(user_profile)
        logger.info("Single user created in vault result: {}".format(res))

        for this_profile in self.durable_profiles:
            this_user = json.loads(this_profile)
            user_profile = {
                "id": this_user["user_id"]["value"],
                "profile": this_profile,
                "primary_username": this_user["primary_username"]["value"],
                "primary_email": this_user["primary_email"]["value"],
                "user_uuid": this_user["uuid"]["value"],
                "sequence_number": "1",
            }
            res = vault.find_or_create(user_profile=user_profile)
            logger.info("Single user created in vault result: {}".format(res))

    def exchange_for_access_token(self):
        conn = http.client.HTTPSConnection("auth.mozilla.auth0.com")
        payload_dict = dict(
            client_id=self.helper_configuration.get_client_id(),
            client_secret=self.helper_configuration.get_client_secret(),
            audience=self.helper_configuration.get_url_dict().get("audience"),
            grant_type="client_credentials",
        )

        payload = json.dumps(payload_dict)
        headers = {"content-type": "application/json"}
        conn.request("POST", "/oauth/token", payload, headers)
        res = conn.getresponse()
        data = json.loads(res.read())
        return data["access_token"]

    def test_paginated_users(self):
        access_token = self.exchange_for_access_token()
        base_url = "person.api.dev.sso.allizom.org"
        conn = http.client.HTTPSConnection(base_url)
        headers = {"authorization": "Bearer {}".format(access_token)}
        conn.request("GET", "/v2/users", headers=headers)
        res = conn.getresponse()
        data = json.loads(res.read())
        return data

    def test_get_single_user(self):
        access_token = self.exchange_for_access_token()
        base_url = "person.api.dev.sso.allizom.org"
        conn = http.client.HTTPSConnection(base_url)
        headers = {"authorization": "Bearer {}".format(access_token)}
        conn.request("GET", "/v2/user/primary_email/dunnkyle%40lam.com", headers=headers)
        res = conn.getresponse()
        data = json.loads(res.read())
        return data

    def test_get_user_ids_for_connection(self):
        access_token = self.exchange_for_access_token()
        base_url = "person.api.dev.sso.allizom.org"
        conn = http.client.HTTPSConnection(base_url)
        headers = {"authorization": "Bearer {}".format(access_token)}
        conn.request("GET", "/v2/users/id/all?connectionMethod=email", headers=headers)
        res = conn.getresponse()
        data = json.loads(res.read())
        assert isinstance(data, list)
        assert len(data) > 0