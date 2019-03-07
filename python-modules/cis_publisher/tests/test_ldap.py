import cis_publisher
import mock
import os


class TestLDAP:
    def setup(self):
        os.environ["CIS_CONFIG_INI"] = "tests/fixture/mozilla-cis.ini"

    @mock.patch("cis_publisher.Publish._request")
    @mock.patch("cis_publisher.secret.Manager.secret")
    @mock.patch("cis_publisher.secret.AuthZero.exchange_for_access_token")
    @mock.patch("cis_publisher.ldap.LDAPPublisher.fetch_from_s3")
    @mock.patch("cis_publisher.publisher.Publish.validate")
    def test_publisher(self, mock_validate, mock_s3, mock_authzero, mock_secrets, mock_request):
        mock_authzero.return_value = "dinopark"
        mock_secrets.return_value = "is_pretty_cool"

        class FakeResponse:
            def ok(self):
                return True

        mock_request.return_value = FakeResponse()
        mock_validate.return_value = True
        with open("tests/fixture/ldap_profiles.json.xz", "rb") as fd:
            mock_s3.return_value = fd.read()
        ldap = cis_publisher.ldap.LDAPPublisher()
        ldap.publish()
