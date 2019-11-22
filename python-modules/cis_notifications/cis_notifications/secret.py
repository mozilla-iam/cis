import boto3
import base64
import http.client
import json
import time
from botocore.exceptions import ClientError
from cis_notifications import common
from logging import getLogger


logger = getLogger(__name__)


class AuthZero(object):
    def __init__(self, client_id, client_secret, api_identifier, authzero_tenant):
        """[summary]

        Arguments:
            object {[type]} -- [an instance of the class.]
            client_id {[type]} -- [The client ID of the auth zero client you would like to use to sign the request.]
            client_secret {[type]} -- [The client secret of the client you would like to use to sign the request.]
            api_identifier {[type]} -- [The audience for the custom authorizer.]
            authzero_tenant {[type]} -- [The auth zero tenant to connect to in order to make the credential exchange.]
        """

        self.client_id = client_id
        self.client_secret = client_secret
        self.api_identifier = api_identifier
        self.authzero_tenant = authzero_tenant

    def exchange_for_access_token(self):
        """[summary]
        Go to the tenant and fetch a bearer token to send in the POST request to the endpoint.  This
        can then be verified on the RP side to prevent SPAM of the endpoint and DOS against the person API
        for a large batch of users.

        Returns:
            [type] -- [a dict with an access token base64 encoded JWT.]
        """
        logger.info(
            "Attempting to exchange for access token with: {}".format(self.authzero_tenant),
            extra={"client_id": self.client_id, "api_identifier": self.api_identifier, "tenant": self.authzero_tenant},
        )
        conn = http.client.HTTPSConnection(self.authzero_tenant)
        payload_dict = dict(
            client_id=self.client_id,
            client_secret=self.client_secret,
            audience=self.api_identifier,
            grant_type="client_credentials",
        )

        payload = json.dumps(payload_dict)
        headers = {"content-type": "application/json"}
        conn.request("POST", "/oauth/token", payload, headers)
        res = conn.getresponse()
        data = json.loads(res.read())
        return data


class Manager(object):
    def __init__(self):
        self.config = common.get_config()
        self.region_name = self.config("secret_manager_ssm_region", namespace="cis", default="us-west-2")
        self.boto_session = boto3.session.Session(region_name=self.region_name)
        self.ssm_client = self.boto_session.client("ssm")
        self.secretsmanager_client = self.boto_session.client("secretsmanager")

    def secretmgr_store(self, secret_name, data):
        """[summary]
        Stores a secret to the secretsmanager store
        Returns:
            [type] -- [A dict if successful, None otherwise]
        """
        result = None
        try:
            namespace = self.config("secret_manager_ssm_path", namespace="cis", default="/iam")
            logger.debug("Secretsmanager storing secret: {}/{}".format(namespace, secret_name))
            result = self.secretsmanager_client.update_secret(
                SecretId="{}/{}".format(namespace, secret_name), SecretString=json.dumps(data)
            )
        except ClientError as e:
            logger.error("Failed to store secret in secretsmanager due to: {}".format(e))
        return result

    def secretmgr(self, secret_name):
        """[summary]
        Fetch a secret from the secretmanager store (not SSM).
        Returns:
            [type] -- [The result of the query (binary, str or dict) or None in the case the secret does not exist.]
        """
        secret = None

        try:
            namespace = self.config("secret_manager_ssm_path", namespace="cis", default="/iam")
            logger.debug("Secretsmanager loading secret: {}/{}".format(namespace, secret_name))
            get_secret_value_response = self.secretsmanager_client.get_secret_value(
                SecretId="{}/{}".format(namespace, secret_name)
            )
        except ClientError as e:
            logger.error("Failed to fetch secret from secretsmanager due to: {}".format(e))
        else:
            logger.debug("Secrets were returned from the secretsmanager")
            # Decrypts secret using the associated KMS CMK.
            # Depending on whether the secret is a string or binary, one of these fields will be populated.
            if "SecretString" in get_secret_value_response:
                secret_str = get_secret_value_response["SecretString"]
                try:
                    secret = json.loads(secret_str)
                except Exception as e:
                    logger.debug(
                        "json.loads of secret failed, wrapping secret string into a dict to look like JSON ({})".format(
                            e
                        )
                    )
                    secret = {"secret": secret_str}
            else:
                logger.debug("Secret is stored in binary, decoding and wrappign it into a dict to look like JSON")
                secret = {"secret": base64.b64decode(get_secret_value_response["SecretBinary"])}
        return secret

    def secret(self, secret_name):
        """[summary]
        Fetch a secret from the ssm parameter store.

        Arguments:
            secret_name {[type]} -- [The name of the parameter to combine with the SSM path variable.]

        Returns:
            [type] -- [The result of the query or None in the case the secret does not exist.]
        """
        result = None
        retry = 5
        backoff = 1  # how long to sleep between attempts.

        while result is None and retry != 0:
            try:
                ssm_namespace = self.config("secret_manager_ssm_path", namespace="cis", default="/iam")
                ssm_response = self.ssm_client.get_parameter(
                    Name="{}/{}".format(ssm_namespace, secret_name), WithDecryption=True
                )
                logger.debug("Secret manager SSM provider loading key: {}{}".format(ssm_namespace, secret_name))
                result = ssm_response.get("Parameter", {})
            except ClientError as e:
                logger.error("Failed to fetch secret due to: {}".format(e))
                retry = retry - 1
                time.sleep(backoff)
                backoff = backoff + 1
                logger.debug("Backing off to try again.")
        logger.debug("Secrets were returned from the function.")
        return result["Value"]
