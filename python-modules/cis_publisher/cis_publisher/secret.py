import boto3
import http.client
import json
import time
from botocore.exceptions import ClientError
from cis_publisher import common
from logging import getLogger


logger = getLogger(__name__)


class AuthZero(object):
    def __init__(self, client_id, client_secret, api_identifier, authzero_tenant):
        """[summary]

        Arguments:
            object {[type]} -- [an instance of the class.]
            client_id {[type]} -- [The client ID of the auth zero client you would like to use to sign the request.]
            client_secret {[type]} -- [The client secret of the client you would like to use to sign the request.]
            authzero_tenant {[type]} -- [The auth zero tenant to connect to in order to make the credential exchange.]
        """

        self.client_id = client_id
        self.client_secret = client_secret
        self.authzero_tenant = authzero_tenant
        self.api_identifier = api_identifier

    def exchange_for_access_token(self):
        """[summary]
        Go to the tenant and fetch a bearer token to send in the POST request to the endpoint.  This
        can then be verified on the RP side to prevent SPAM of the endpoint and DOS against the person API
        for a large batch of users.

        Returns:
            [type] -- [an access token base64 encoded JWT.]
        """
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
        if res.status > 299 or res.status < 200:
            logger.error("Failed to exchange access token. status: {} text: {}".format(res.status, data))

        return data["access_token"]


class Manager(object):
    def __init__(self):
        self.config = common.get_config()
        self.region_name = self.config("secret_manager_ssm_region", namespace="cis", default="us-west-2")
        self.boto_session = boto3.session.Session(region_name=self.region_name)
        self.ssm_client = self.boto_session.client("ssm")
        self._cache = {}

    def secret(self, secret_name):
        """[summary]
        Fetch a secret from the ssm parameter store.

        Arguments:
            secret_name {[type]} -- [The name of the parameter to combine with the SSM path variable.]

        Returns:
            [type] -- [The result of the query or None in the case the secret does not exist.]
        """
        if secret_name in self._cache:
            logger.debug("Returning memory-cached version of the parameter: {}".format(secret_name))
            return self._cache[secret_name]

        result = None
        retry = 5
        backoff = 1  # how long to sleep between attempts

        # XXX this should use:
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ssm.html#SSM.Client.get_waiter
        while result is None and retry != 0:
            try:
                ssm_namespace = self.config("secret_manager_ssm_path", namespace="cis", default="/iam")
                ssm_response = self.ssm_client.get_parameter(
                    Name="{}/{}".format(ssm_namespace, secret_name), WithDecryption=True
                )
                logger.debug("Secret manager SSM provider loading key: {}:{}".format(ssm_namespace, secret_name))
                result = ssm_response.get("Parameter", {})
            except ClientError as e:
                logger.error("Failed to fetch secret due to: {}".format(e))
                retry = retry - 1
                time.sleep(backoff)
                backoff = backoff + 1
                logger.debug("Backing off to try again.")

        self._cache[secret_name] = result["Value"]
        logger.debug("Secrets were fetched successfully from the function.")
        return self._cache[secret_name]
