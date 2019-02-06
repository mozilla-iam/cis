"""Class for following a default provider chain in the fetching of key material for sign/verify operations."""
import boto3
import json
import os
import logging
from cis_crypto import common
from jose import jwk


logger = logging.getLogger(__name__)


class Manager(object):
    """Top level manager object.  Will instantiate the appropriate provider based on configuration."""

    def __init__(self, provider_type):
        self.provider_type = provider_type

    def get_key(self, key_name):
        provider = self._load_provider()
        return provider.key(key_name)

    def _load_provider(self):
        logger.debug("Using secret manager provider type: {}".format(self.provider_type))
        if self.provider_type.lower() == "file":
            return FileProvider()
        elif self.provider_type.lower() == "aws-ssm":
            return AWSParameterstoreProvider()
        else:
            raise ValueError("The secret provider selected is not yet supported file|aws-ssm are currently available.")


class FileProvider(object):
    """Support loading key material from disk."""

    def key(self, key_name):
        """Takes key_name returns bytes"""
        config = common.get_config()
        key_dir = config(
            "secret_manager_file_path",
            namespace="cis",
            default=("{}/.mozilla-iam/keys/".format(os.path.expanduser("~"))),
        )
        file_name = "{}".format(key_name)
        logger.debug("Secret manager file provider loading key file: {}/{}".format(key_dir, key_name))
        fh = open((os.path.join(key_dir, file_name)), "rb")
        key_content = fh.read()
        key_construct = jwk.construct(key_content, "RS256")
        return key_construct


class AWSParameterstoreProvider(object):
    """Support loading secure strings from AWS parameter store."""

    def __init__(self):
        self.config = common.get_config()
        self.region_name = self.config("secret_manager_ssm_region", namespace="cis", default="us-west-2")
        self.boto_session = boto3.session.Session(region_name=self.region_name)
        self.ssm_client = self.boto_session.client("ssm")

    def key(self, key_name):
        ssm_namespace = self.config("secret_manager_ssm_path", namespace="cis", default="/iam")
        ssm_response = self.ssm_client.get_parameter(Name="{}/{}".format(ssm_namespace, key_name), WithDecryption=True)

        logger.debug("Secret manager SSM provider loading key: {}:{}".format(ssm_namespace, key_name))

        result = ssm_response.get("Parameter")
        try:
            key_dict = json.loads(result.get("Value"))
            key_construct = jwk.construct(key_dict, "RS256")
        except json.decoder.JSONDecodeError:
            key_construct = jwk.construct(result.get("Value"), "RS256")
        return key_construct
