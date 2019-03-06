import cis_publisher
import cis_profile
import os


class TestPublisher:
    def setup(self):
        os.environ["CIS_CONFIG_INI"] = "tests/fixture/mozilla-cis.ini"

    def test_get_wk(self):
        profiles = [cis_profile.User()]
        publisher = cis_publisher.Publish(profiles)
        publisher.get_api_urls()
        assert isinstance(publisher, object)
        assert publisher.api_url is not None

    def test_profile_validate(self):
        profiles = [cis_profile.User()]
        publisher = cis_publisher.Publish(profiles)
        publisher.validate()
