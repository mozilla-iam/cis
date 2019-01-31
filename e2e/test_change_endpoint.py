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
    u = helpers.ensure_appropriate_publishers_and_sign(fake_profile=u, condition='create')
    u.verify_all_publishers(profile.User(user_structure_json=None))
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

"""
def test_publishing_profiles_it_should_be_accepted():
    os.environ["CIS_SECRET_MANAGER_SSM_PATH"] = "/iam/cis/{}".format(os.getenv('CIS_ENVIRONMENT', 'development'))
    base_url = helpers.get_url_dict().get('change')
    profiles = []
    publishers = ['ldap', 'cis', 'access_provider', 'mozilliansorg', 'hris']
    while len(profiles) != 5:
        u = fake_profile.FakeUser()
        try:
            u = helpers.ensure_appropriate_publishers(fake_profile=u, condition='create')
            u.verify_all_publishers(previous_user=profile.User())
            os.environ['CIS_SECRET_MANAGER'] = 'aws-ssm'
            os.environ['CIS_SECRET_MANAGER_SSM_PATH'] = '/iam/cis/{}'.format(os.getenv('CIS_ENVIRONMENT', 'development'))
            os.environ['CIS_SIGNING_KEY_NAME'] = 'mozilliansorg_signing_key'

            u = u.as_dict()
            u = profile.User(user_structure_json=u)
            u.sign_all(publisher_name='mozilliansorg')

            os.environ['CIS_SIGNING_KEY_NAME'] = 'hris_signing_key'

            u = u.as_dict()
            u = profile.User(user_structure_json=u)
            u.sign_all(publisher_name='hris')

            os.environ['CIS_SIGNING_KEY_NAME'] = 'ldap_signing_key'

            u = u.as_dict()
            u = profile.User(user_structure_json=u)
            u.sign_all(publisher_name='ldap')

            os.environ['CIS_SIGNING_KEY_NAME'] = 'auth0_signing_key'

            u = u.as_dict()
            print(u['user_id'])
            u = profile.User(user_structure_json=u)
            u.sign_all(publisher_name='access_provider')

            os.environ['CIS_SIGNING_KEY_NAME'] = 'change_service_signing_key'

            u = u.as_dict()
            u = profile.User(user_structure_json=u)
            u.sign_all(publisher_name='cis')
            print(u['user_id'])

            profiles.append(u.as_json())
        except PublisherVerificationFailure:
            pass

    wk = WellKnown()
    access_token = exchange_for_access_token()
    conn = http.client.HTTPSConnection(base_url)
    headers = {"authorization": "Bearer {}".format(access_token), "Content-type": "application/json"}
    conn.request("POST", "/v2/users", json.dumps(profiles), headers=headers)
    res = conn.getresponse()
    data = json.loads(res.read().decode())
    assert data[0].get('sequence_numbers') is not None
    assert data[0].get('status') == 200
"""
