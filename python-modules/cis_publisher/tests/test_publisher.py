import cis_publisher
import mock
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

    @mock.patch("cis_publisher.Publish._request")
    @mock.patch("cis_publisher.secret.Manager.secret")
    @mock.patch("cis_publisher.secret.AuthZero.exchange_for_access_token")
    def test_post(self, mock_authzero, mock_secrets, mock_request):
        mock_authzero.return_value = "dinopark"
        mock_secrets.return_value = "is_pretty_cool"

        class FakeResponse:
            def ok(self):
                return True

        mock_request.return_value = FakeResponse()
        profiles = [cis_profile.User()]
        publisher = cis_publisher.Publish(profiles)
        publisher.post_all()
