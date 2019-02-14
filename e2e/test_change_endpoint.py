import json
import jsonschema
import http.client
import logging
import os
import random
from . import helpers
import cis_crypto
from cis_profile import common
from cis_profile import fake_profile
from cis_profile import profile
from cis_profile import WellKnown
from cis_profile.exceptions import PublisherVerificationFailure


logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("botocore").setLevel(logging.CRITICAL)


class TestChangeEndpoint(object):
    def setup(self):
        u = fake_profile.FakeUser()
        u = helpers.ensure_appropriate_publishers_and_sign(fake_profile=u, condition="create")
        u.verify_all_publishers(profile.User(user_structure_json=None))
        self.durable_profile = u.as_json()

    def exchange_for_access_token(self):
        conn = http.client.HTTPSConnection("auth.mozilla.auth0.com")
        payload_dict = dict(
            client_id=helpers.get_client_id(),
            client_secret=helpers.get_client_secret(),
            audience=helpers.get_url_dict().get("audience"),
            grant_type="client_credentials",
        )

        payload = json.dumps(payload_dict)
        headers = {"content-type": "application/json"}
        conn.request("POST", "/oauth/token", payload, headers)
        res = conn.getresponse()
        data = json.loads(res.read())
        return data["access_token"]

    def test_publishing_a_profile_it_should_be_accepted(self):
        base_url = helpers.get_url_dict().get("change")
        wk = WellKnown(discovery_url="https://auth.allizom.org/.well-known/mozilla-iam")
        jsonschema.validate(json.loads(self.durable_profile), wk.get_schema())
        os.environ["CIS_WELL_KNOWN_MODE"] = "https"
        os.environ["CIS_PUBLIC_KEY_NAME"] = "publisher"
        user = profile.User(
            user_structure_json=json.loads(self.durable_profile),
            discovery_url="https://auth.allizom.org/.well-known/mozilla-iam",
        )
        user.verify_all_signatures()
        access_token = self.exchange_for_access_token()
        conn = http.client.HTTPSConnection(base_url)
        logger.info("Attempting connection for: {}".format(base_url))
        headers = {"authorization": "Bearer {}".format(access_token), "Content-type": "application/json"}
        conn.request("POST", "/v2/user", self.durable_profile, headers=headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode())
        logger.info(data)
        assert data.get("status") == 200
        assert data.get("sequence_number") is not None

    def test_publishing_a_profile_using_a_partial_update(self):
        base_url = helpers.get_url_dict().get("change")
        wk = WellKnown(discovery_url="https://auth.allizom.org/.well-known/mozilla-iam")
        jsonschema.validate(json.loads(self.durable_profile), wk.get_schema())
        os.environ["CIS_WELL_KNOWN_MODE"] = "https"
        os.environ["CIS_PUBLIC_KEY_NAME"] = "publisher"
        user = profile.User(
            user_structure_json=json.loads(self.durable_profile),
            discovery_url="https://auth.allizom.org/.well-known/mozilla-iam",
        )
        user.verify_all_signatures()
        access_token = self.exchange_for_access_token()
        conn = http.client.HTTPSConnection(base_url)
        logger.info("Attempting connection for: {}".format(base_url))
        headers = {"authorization": "Bearer {}".format(access_token), "Content-type": "application/json"}
        conn.request("POST", "/v2/user", self.durable_profile, headers=headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode())
        logger.info(data)

        partial_update = profile.User(user_structure_json=None)
        partial_update.user_id = user.user_id
        partial_update.uuid = user.uuid
        partial_update.primary_email = user.primary_email
        partial_update.primary_username = user.primary_username
        partial_update.first_name.value = "anewfirstname"
        partial_update.sign_attribute("first_name", "mozilliansorg")

        logger.info("Attempting connection for: {}".format(base_url))
        headers = {"authorization": "Bearer {}".format(access_token), "Content-type": "application/json"}
        conn.request("POST", "/v2/user", partial_update.as_json(), headers=headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode())
        assert data.get("status") == 200
        assert data.get("sequence_number") is not None

    def test_deleting_a_profile(self):
        base_url = helpers.get_url_dict().get("change")
        if os.getenv("CIS_ENVIRONMENT", "development") == "development":
            wk = WellKnown()
            access_token = self.exchange_for_access_token()
            conn = http.client.HTTPSConnection(base_url)
            headers = {"authorization": "Bearer {}".format(access_token), "Content-type": "application/json"}
            conn.request("DELETE", "/v2/user", self.durable_profile, headers=headers)
            res = conn.getresponse()
            data = json.loads(res.read().decode())
            logger.info(data)
        else:
            pass
