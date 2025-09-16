"""
n.b. Do not run this as a part of your development cycle. Do not run this
regularly. This can, and will, insert weird data into CIS, if misconfigured.

A pseudo-e2e test, where we run the code locally but use dev/stage resources.
This is the code equivalent of running with scissors.

Requires the following environment variables:

    CIS_ENVIRONMENT="testing"
    CIS_SEED_API_DATA="false"
    PERSON_API_ADVANCED_SEARCH="true"
    PERSON_API_INITIALIZE_VAULT="false"
    PERSON_API_JWT_VALIDATION="false"
    SERVER_NAME="127.0.0.1:8000"

Run the server with:

    python cis_profile_retrieval_service/v2_api.py

Run the test with:

    PSEUDO_E2E=yes pytest --log-cli-level=DEBUG tests/test_e2e.py

You'll also need an active AWS session, which is left as an exercise for the
user.
"""

import logging
import os
import pytest
import requests

from tests.fake_auth0 import FakeBearer

logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")
logging.getLogger("faker.factory").setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture
def auth_headers():
    bearer = FakeBearer()
    token = bearer.generate_bearer_with_scope("display:all search:all")
    headers = {"Authorization": f"Bearer {token}"}
    return headers


@pytest.mark.skipif(os.environ.get("PSEUDO_E2E") is None, reason="Not running in pseudo-E2E mode.")
def test_retrieve_single_profile(auth_headers):
    res = requests.get(
        "http://localhost:8000/v2/users/id/all?connectionMethod=ad&active=True",
        headers=auth_headers,
    ).json()
    next_page = res.get("nextPage")
    pages = 1
    while next_page:
        res = requests.get(
            f"http://localhost:8000/v2/users/id/all?connectionMethod=ad&active=True&nextPage={next_page}",
            headers=auth_headers,
        ).json()
        next_page = res.get("nextPage")
        pages += 1
    assert pages >= 2, "Did not iterate through any pages."
