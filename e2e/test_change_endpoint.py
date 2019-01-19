import boto3
import json
import jsonschema
import http.client
import os
from cis_profile import fake_profile
from cis_profile import WellKnown


cis_environment = os.getenv("CIS_ENVIRONMENT", "testing")
client_id_name = "/iam/cis/{}/change_client_id".format(cis_environment)
client_secret_name = "/iam/cis/{}/change_service_client_secret".format(cis_environment)

if cis_environment == "testing":
    base_url = "change.api.test.sso.allizom.org"
elif cis_environment == "development":
    base_url = "change.api.dev.sso.allizom.org"
elif cis_environment == "production":
    base_url == "change.api.sso.mozilla.com"

client = boto3.client("ssm")


def get_secure_parameter(parameter_name):
    response = client.get_parameter(Name=parameter_name, WithDecryption=True)
    return response["Parameter"]["Value"]


def get_client_secret():
    return get_secure_parameter(client_secret_name)


def get_client_id():
    return get_secure_parameter(client_id_name)


def exchange_for_access_token():
    conn = http.client.HTTPSConnection("auth.mozilla.auth0.com")
    payload_dict = dict(
        client_id=get_client_id(),
        client_secret=get_client_secret(),
        audience="api.test.sso.allizom.org",
        grant_type="client_credentials",
    )

    payload = json.dumps(payload_dict)
    headers = {"content-type": "application/json"}
    conn.request("POST", "/oauth/token", payload, headers)
    res = conn.getresponse()
    data = json.loads(res.read())
    return data["access_token"]


def test_api_is_alive():
    access_token = exchange_for_access_token()
    conn = http.client.HTTPSConnection(base_url)
    headers = {"authorization": "Bearer {}".format(access_token)}
    conn.request("GET", "/v2/user/status?sequenceNumber=123456", headers=headers)
    res = conn.getresponse()
    data = json.loads(res.read())
    assert data["identity_vault"] is not None


def test_publishing_a_profile_it_should_be_accepted():
    u = fake_profile.FakeUser()
    json_payload = u.as_json()
    wk = WellKnown()
    jsonschema.validate(json.loads(json_payload), wk.get_schema())
    access_token = exchange_for_access_token()
    conn = http.client.HTTPSConnection(base_url)
    headers = {"authorization": "Bearer {}".format(access_token), "Content-type": "application/json"}
    conn.request("POST", "/v2/user", json_payload, headers=headers)
    res = conn.getresponse()
    data = res.read()
    return data


def test_publishing_profiles_it_should_be_accepted():
    profiles = []
    for x in range(0, 4):
        u = fake_profile.FakeUser()
        profiles.append(u.as_json())
    wk = WellKnown()
    access_token = exchange_for_access_token()
    conn = http.client.HTTPSConnection(base_url)
    headers = {"authorization": "Bearer {}".format(access_token), "Content-type": "application/json"}
    conn.request("POST", "/v2/users", json.dumps(profiles), headers=headers)
    res = conn.getresponse()
    data = res.read()
    return data


if __name__ == "__main__":
    print("test_publishing_a_profile_it_should_be_accepted:", test_publishing_a_profile_it_should_be_accepted())
    print("test_publishing_profiles_it_should_be_accepted:", test_publishing_profiles_it_should_be_accepted())
