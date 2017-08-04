"""Centralized handling of AWS Boto sessions for change integration."""

import boto3
import logging


logger = logging.getLogger(__name__)


class Connect(object):
    def __init__(self, connection_type='session', service=None, region='us-west-2', profile='default'):
        """
        :param connection_type: session|client|resource
        :param service: kms|dynamodb|other
        :param region: us-east-1|us-west-2
        :param profile: default but supports others
        """
        self.service = service
        self.region = region
        self.connection_type = connection_type
        self.profile = profile

        boto3.setup_default_session(profile_name=self.profile)

    def connect(self):
        if self.connection_type == "client":
            client = boto3.client(
                self.service,
                region_name=self.region
            )
            self.client = client
            return self.client
        elif self.connection_type == "resource":
            resource = boto3.resource(
                self.service,
                region_name=self.region
            )
            self.resource = resource
            return self.resource
        elif self.connection_type == "session":
            session = boto3.Session(
                region_name=self.region,
                profile_name=self.profile
            )
            return session
        else:
            raise AttributeError(
                "Connection type is not supported."
            )
