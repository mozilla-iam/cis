import cis_publisher
import mock
import cis_profile
import os


class TestPublisher:
    def setup(self):
        os.environ["CIS_CONFIG_INI"] = "tests/fixture/mozilla-cis.ini"

    def test_obj(self):
        profiles = [cis_profile.User()]
        publisher = cis_publisher.Publish(profiles, login_method="ad", publisher_name="ldap")
        assert isinstance(publisher, object)

    @mock.patch("cis_publisher.secret.Manager.secret")
    @mock.patch("cis_publisher.secret.AuthZero.exchange_for_access_token")
    @mock.patch("cis_publisher.Publish._request_get")
    def test_known_users(self, mock_request_get, mock_authzero, mock_secrets):
        mock_secrets.return_value = "hi"
        mock_authzero.return_value = "hi"

        class FakeResponse:
            def __init__(self, fake={}):
                self.fake = fake
                self.text = str(fake)

            def json(self):
                return self.fake

            def ok(self):
                return True

        mu = [{"user_id": "auser", "uuid": "093249324", "primary_email": "auser@u.net"}]
        mock_request_get.return_value = FakeResponse(fake=mu)

        profiles = [cis_profile.User()]
        publisher = cis_publisher.Publish(profiles, login_method="ad", publisher_name="ldap")
        u = publisher.get_known_cis_users()
        assert u == mu

    def test_profile_validate(self):
        profiles = [cis_profile.User()]
        publisher = cis_publisher.Publish(profiles, login_method="ad", publisher_name="ldap")
        publisher.validate()

    @mock.patch("cis_publisher.Publish._request_post")
    @mock.patch("cis_publisher.secret.Manager.secret")
    @mock.patch("cis_publisher.secret.AuthZero.exchange_for_access_token")
    def test_post(self, mock_authzero, mock_secrets, mock_request_post):
        mock_authzero.return_value = "dinopark"
        mock_secrets.return_value = "is_pretty_cool"

        class FakeResponse:
            def ok(self):
                return True

        mock_request_post.return_value = FakeResponse()
        profiles = [cis_profile.User()]
        cis_publisher.Publish(profiles, login_method="ad", publisher_name="ldap")

    @mock.patch("cis_publisher.Publish._request_post")
    @mock.patch("cis_publisher.Publish._request_get")
    @mock.patch("cis_publisher.secret.Manager.secret")
    @mock.patch("cis_publisher.secret.AuthZero.exchange_for_access_token")
    @mock.patch("cis_publisher.Publish.validate")
    def test_post_specific_user(self, mock_validate, mock_authzero, mock_secrets, mock_request_get, mock_request_post):
        mock_authzero.return_value = "dinopark"
        mock_secrets.return_value = "is_pretty_cool"
        mock_validate.return_value = True

        class FakeResponse:
            def __init__(self, fake={}):
                self.fake = fake
                self.text = str(fake)

            def json(self):
                return self.fake

            def ok(self):
                return True

        mock_request_post.return_value = FakeResponse()
        mock_request_get.return_value = FakeResponse()
        profiles = [cis_profile.User(user_id="test")]
        publisher = cis_publisher.Publish(profiles, login_method="ad", publisher_name="ldap")
        publisher.post_all(user_ids=["test"])
        assert publisher.profiles[0].user_id.value == "test"

    @mock.patch("cis_publisher.Publish._request_post")
    @mock.patch("cis_publisher.Publish._request_get")
    @mock.patch("cis_publisher.secret.Manager.secret")
    @mock.patch("cis_publisher.secret.AuthZero.exchange_for_access_token")
    def test_filter_cis_users(self, mock_authzero, mock_secrets, mock_request_get, mock_request_post):
        mock_authzero.return_value = "dinopark"
        mock_secrets.return_value = "is_pretty_cool"

        class FakeResponse:
            def __init__(self, fake={}):
                self.fake = fake
                self.text = str(fake)

            def json(self):
                return self.fake

            def ok(self):
                return True

        mock_request_post.return_value = FakeResponse()
        mu = [{"user_id": "auser", "uuid": "0932493241", "primary_email": "auser@u.net"}]
        mock_request_get.return_value = FakeResponse(fake=mu)

        profiles = [cis_profile.User()]
        profiles[0].user_id.value = "auser"
        profiles[0].first_name.value = "firstname"
        profiles[0].first_name.signature.publisher.name = "wrong"
        publisher = cis_publisher.Publish(profiles, login_method="ad", publisher_name="ldap")
        publisher.filter_known_cis_users()

        assert publisher.profiles[0].first_name.value != "firstname"
