import boto3
import json
import logging
import os
import subprocess
from mock import patch
from moto import mock_dynamodb2
from moto import mock_sts
from tests.fake_auth0 import FakeBearer
from tests.fake_auth0 import json_form_of_pk


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s:%(message)s'
)

logging.getLogger('boto').setLevel(logging.CRITICAL)
logging.getLogger('boto3').setLevel(logging.CRITICAL)
logging.getLogger('botocore').setLevel(logging.CRITICAL)


logger = logging.getLogger(__name__)


class TestAPI(object):
    def setup_class(self):
        os.environ['CIS_CONFIG_INI'] = 'tests/mozilla-cis.ini'
        dynalite_port = '34567'
        self.dynaliteprocess = subprocess.Popen(['dynalite', '--port', dynalite_port], preexec_fn=os.setsid)

        from cis_hris_api import v2_api as api
        from cis_hris_api import common
        from cis_hris_api import user
        common.create(common.connect())
        self.table = common.get_table_resource()
        profile = user.Profile(self.table)
        fh = open('tests/fixture/workday.json')
        file_content = json.loads(fh.read())
        fh.close()
        profile.seed(file_content)
        api.app.testing = True
        self.app = api.app.test_client()

    def test_that_we_seeded_the_table(self):
        os.environ['CIS_CONFIG_INI'] = 'tests/mozilla-cis.ini'
        from cis_hris_api import user
        profile = user.Profile(self.table)
        profiles = profile.all
        assert len(profiles) >= 2

    def test_flask_graphql_query(self):
        os.environ['CIS_CONFIG_INI'] = 'tests/mozilla-cis.ini'
        payload = 'query {profile (primary_email: "iam_test@mozilla.com") {primary_email}}'
        result = self.app.get(
            '/graphql?query={}'.format(payload),
            follow_redirects=True
        )
        response = json.loads(result.get_data())
        assert response['data']['profile']['primary_email'] == 'iam_test@mozilla.com'

    def teardown_class(self):
        os.killpg(os.getpgid(self.dynaliteprocess.pid), 15)
