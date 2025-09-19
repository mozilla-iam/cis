"""
A simplification of the existing v2_api tests. There's care to reuse Dynamo and
the users we create across each test, since otherwise it'll take a while when
adding additional tests.

See `DEBT` notes for where I ran into weirdness.

Run with:

    pytest --log-cli-level=DEBUG tests/test_v2_api_pagination.py

"""

import logging
import os

import pytest
import boto3
from moto import mock_aws
from tests.fake_auth0 import FakeBearer, json_form_of_pk

from cis_identity_vault import vault

logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")

# Set to the level where logs become interesting, otherwise our log output
# becomes too verbose. A pain while testing iteratively.
logging.getLogger("boto3").setLevel(logging.INFO)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("faker").setLevel(logging.INFO)
logging.getLogger("everett").setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)
logging.getLogger("responses").setLevel(logging.WARNING)
logging.getLogger("cis_profile").setLevel(logging.INFO)
logging.getLogger("cis_identity_vault.parallel_dynamo").setLevel(logging.INFO)

logger = logging.getLogger(__name__)


# Re-use our AWS mocks module-wide. Related to `identity_vault`.
def setup_module(module):
    module.mock = mock_aws(config={"core": {"service_whitelist": ["dynamodb"]}})
    module.mock.start()


def teardown_module(module):
    module.mock.stop()


@pytest.fixture(scope="module")
def environment():
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("CIS_CONFIG_INI", "tests/mozilla-cis-mock.ini")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")
        yield monkeypatch


# Slow, so reuse across the module.
@pytest.fixture(scope="module")
def identity_vault(environment):
    vault_client = vault.IdentityVault()
    vault_client.connect()
    vault_client.create()
    vault_client.find_or_create()
    # DEBT: requires side-effects.
    from cis_profile_retrieval_service.common import seed

    # DEBT: doesn't generate `ad|Mozilla-LDAP` users.
    seed(number_of_fake_users=256)
    return (boto3.client("dynamodb"), boto3.resource("dynamodb"))


@pytest.fixture
def app(environment, monkeypatch):
    bearer = FakeBearer()
    token = bearer.generate_bearer_with_scope("display:all search:all")
    headers = {"Authorization": f"Bearer {token}"}
    monkeypatch.setattr("cis_profile_retrieval_service.idp.get_jwks", lambda: json_form_of_pk)
    # DEBT: requires side-effects.
    from cis_profile_retrieval_service import v2_api

    v2_api.app.testing = True
    return (headers, v2_api.app.test_client())


def test_existing(identity_vault, app):
    """
    As it turns out, our pagination was broken.

    The `v2/users/id/all` endpoint, as written, did the right thing: paginate
    through pages, skipping empty pages.

    The scan logic [0] has a slight bug in it, where it would continue
    paginating. Since it was doing this pagination for us, at a lower level, we
    simply weren't propagating any `nextPage` tokens forward.

    Pagination mystery: solved.

    [0]: python-modules/cis_identity_vault/cis_identity_vault/parallel_dynamo.py
    """
    headers, client = app
    # DEBT: see note above, about not generating `ad|Mozilla-LDAP` users.
    results = client.get(
        "/v2/users/id/all?connectionMethod=github&active=True",
        headers=headers,
        follow_redirects=True,
    ).json
    next_page = results.get("nextPage")
    pages = 1
    # Pagination, as implemented elsewhere.
    while next_page:
        results = client.get(
            f"/v2/users/id/all?connectionMethod=github&active=True&nextPage={next_page}",
            headers=headers,
            follow_redirects=True,
        ).json
        next_page = results.get("nextPage")
        pages += 1
    assert pages >= 2, "Did not paginate!"
