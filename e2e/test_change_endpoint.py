import json
import jsonschema
import http.client
import logging
from . import helpers
from cis_profile import fake_profile
from cis_profile import WellKnown


logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)


def exchange_for_access_token():
    conn = http.client.HTTPSConnection("auth.mozilla.auth0.com")
    payload_dict = dict(
        client_id=helpers.get_client_id(),
        client_secret=helpers.get_client_secret(),
        audience=helpers.get_url_dict().get('audience'),
        grant_type="client_credentials",
    )

    payload = json.dumps(payload_dict)
    headers = {"content-type": "application/json"}
    conn.request("POST", "/oauth/token", payload, headers)
    res = conn.getresponse()
    data = json.loads(res.read())
    return data["access_token"]


def test_publishing_a_profile_it_should_be_accepted():
    base_url = helpers.get_url_dict().get('change')
    u = fake_profile.FakeUser()
    json_payload = u.as_json()
    wk = WellKnown()
    jsonschema.validate(json.loads(json_payload), wk.get_schema())
    access_token = exchange_for_access_token()
    conn = http.client.HTTPSConnection(base_url)
    logger.info('Attempting connection for: {}'.format(base_url))
    headers = {"authorization": "Bearer {}".format(access_token), "Content-type": "application/json"}
    conn.request("POST", "/v2/user", json_payload, headers=headers)
    res = conn.getresponse()
    data = json.loads(res.read().decode())
    assert data.get('status') == 200
    assert data.get('sequence_number') is not None


def test_publishing_profiles_it_should_be_accepted():
    base_url = helpers.get_url_dict().get('change')
    profiles = []
    while len(profiles) != 5:
        u = fake_profile.FakeUser()
        if u.verify_all_publishers(u):
            print(u.verify_all_publishers(u))
            profiles.append(u.as_json())
    wk = WellKnown()
    access_token = exchange_for_access_token()
    conn = http.client.HTTPSConnection(base_url)
    headers = {"authorization": "Bearer {}".format(access_token), "Content-type": "application/json"}
    conn.request("POST", "/v2/users", json.dumps(profiles), headers=headers)
    res = conn.getresponse()
    data = json.loads(res.read().decode())
    print(data)
    assert data[0].get('sequence_numbers') is not None
    assert data[0].get('status') == 200
