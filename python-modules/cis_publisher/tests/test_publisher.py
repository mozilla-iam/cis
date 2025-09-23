import cis_publisher
import cis_profile
import os
from unittest import mock


class TestPublisher:
    def setup(self):
        os.environ["CIS_CONFIG_INI"] = "tests/fixture/mozilla-cis.ini"
        self.mu = {
            "users": [{"user_id": "auser", "uuid": "0932493241", "primary_email": "auser@u.net"}],
            "nextPage": None,
        }
        self.mu2 = {
            "users": [
                {"id": {"value": "auser"}, "uuid": {"value": "0932493241"}, "primary_email": {"value": "auser@u.net"}}
            ],
            "nextPage": None,
        }

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
                self.ok = True

            def json(self):
                return self.fake

        mock_request_get.return_value = FakeResponse(fake=self.mu)

        profiles = [cis_profile.User()]
        publisher = cis_publisher.Publish(profiles, login_method="ad", publisher_name="ldap")
        u = publisher.get_known_cis_users()
        assert u == self.mu["users"]

    @mock.patch("cis_publisher.secret.Manager.secret")
    @mock.patch("cis_publisher.secret.AuthZero.exchange_for_access_token")
    @mock.patch("cis_publisher.Publish._request_get")
    def test_known_users_by_attribute(self, mock_request_get, mock_authzero, mock_secrets):
        mock_secrets.return_value = "hi"
        mock_authzero.return_value = "hi"

        class FakeResponse:
            def __init__(self, fake={}):
                self.fake = fake
                self.text = str(fake)
                self.ok = True

            def json(self):
                return self.fake

        mock_request_get.return_value = FakeResponse(fake=self.mu2)

        profiles = [cis_profile.User()]
        publisher = cis_publisher.Publish(profiles, login_method="ad", publisher_name="ldap")
        attributes = {"staff_information.staff": True, "active": True}
        u = publisher.get_known_cis_user_by_attribute_paginated(attributes)
        print(u)
        assert u["auser"] == self.mu2["users"][0]

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
            def __init__(self):
                self.ok = True

        mock_request_post.return_value = FakeResponse()
        profiles = [cis_profile.User()]
        cis_publisher.Publish(profiles, login_method="ad", publisher_name="ldap")

    @mock.patch("cis_publisher.Publish._request_post")
    @mock.patch("cis_publisher.Publish._request_get")
    @mock.patch("cis_publisher.secret.Manager.secret")
    @mock.patch("cis_publisher.secret.AuthZero.exchange_for_access_token")
    def test_create_bad(self, mock_authzero, mock_secrets, mock_request_get, mock_request_post):
        """
        test that we'll correctly fixup profiles on creation
        """
        mock_authzero.return_value = "dinopark"
        mock_secrets.return_value = "is_pretty_cool"

        class FakeResponse:
            def __init__(self, fake={}):
                self.fake = fake
                self.text = str(fake)
                self.ok = True

            def json(self):
                return self.fake

        mock_request_post.return_value = FakeResponse()
        mock_request_get.return_value = FakeResponse(fake=self.mu)

        u = cis_profile.User()
        # Bad bad
        u.user_id.value = "anotherauser"
        u.fun_title.metadata.display = "private"
        u.fun_title.value = None
        profiles = [u]
        publisher = cis_publisher.Publish(profiles, login_method="ad", publisher_name="ldap")
        publisher.filter_known_cis_users(profiles)
        assert publisher.profiles[0].fun_title.metadata.display != "private"

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
                self.ok = True
                self.status_code = 200

            def json(self):
                return self.fake

        mock_request_post.return_value = FakeResponse()
        mock_request_get.return_value = FakeResponse(fake=self.mu)
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
                self.ok = True

            def json(self):
                return self.fake

        mock_request_post.return_value = FakeResponse()
        mock_request_get.return_value = FakeResponse(fake=self.mu)

        profiles = [cis_profile.User()]
        profiles[0].user_id.value = "auser"

        profiles[0].first_name.value = "firstname"
        profiles[0].first_name.signature.publisher.name = "wrong"

        profiles[0].access_information.hris.values = {"test": "test"}
        profiles[0].access_information.hris.signature.publisher.name = "wrong"

        profiles[0].access_information.ldap.values = {"test": "test"}
        profiles[0].access_information.ldap.signature.publisher.name = "ldap"

        publisher = cis_publisher.Publish(profiles, login_method="ad", publisher_name="ldap")
        publisher.filter_known_cis_users()

        # Should be filtered out because publisher = "wrong"
        assert publisher.profiles[0].first_name.value != "firstname"
        # Should not because publisher = "ldap" and thats "us"
        assert publisher.profiles[0].as_dict()["access_information"]["ldap"]["values"] == {"test": "test"}
        # Should be filtered out because publisher = "wrong"
        assert publisher.profiles[0].as_dict()["access_information"]["hris"]["values"] is None
