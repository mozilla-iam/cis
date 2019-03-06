import boto3
from moto import mock_ssm
from os import environ


class TestAccessTokenExchange(object):
    def test_token_exchange(self):
        pass


@mock_ssm
class TestSecret(object):
    def test_secret_manager(self):
        self.secret_name = "dinosecret"
        client = boto3.client("ssm", region_name="us-west-2")
        client.put_parameter(
            Name="/baz/{}".format(self.secret_name),
            Description="A secret about Dinos.",
            Value="adinosecret",
            Type="SecureString",
            KeyId="alias/aws/ssm",
        )

        from cis_publisher import secret

        environ["CIS_SECRET_MANAGER_SSM_PATH"] = "/baz"
        manager = secret.Manager()
        result = manager.secret("dinosecret")
        assert result == "adinosecret"
