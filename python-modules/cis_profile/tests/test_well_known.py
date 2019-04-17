from cis_profile.common import WellKnown
from cis_profile.profile import User
import os


class Test_WellKnown(object):
    def test_wellknown_file_force(self):
        wk = WellKnown(always_use_local_file=True)
        data = wk.get_well_known()
        assert isinstance(data, dict)
        assert isinstance(data.get("api"), dict)

    def test_wellknown_retrieve(self):
        wk = WellKnown()
        data = wk.get_well_known()
        assert isinstance(data, dict)
        assert isinstance(data.get("api"), dict)

    def test_schema_retrieve(self):
        wk = WellKnown()
        data = wk.get_schema()
        assert isinstance(data, dict)

    def test_rules_retrieve(self):
        wk = WellKnown()
        data = wk.get_publisher_rules()
        assert isinstance(data, dict)
        assert isinstance(data.get("create"), dict)

    def test_profile_env(self):
        os.environ["CIS_DISCOVERY_URL"] = "https://auth.allizom.org/.well-known/mozilla-iam"
        u = User()
        assert u._User__well_known.discovery_url == "https://auth.allizom.org/.well-known/mozilla-iam"
