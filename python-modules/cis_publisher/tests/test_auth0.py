import cis_publisher

# import cis_profile
import logging

import json

# import mock

# from moto import mock_aws
# from unittest import boto3

logging.getLogger("cis_publisher").setLevel(logging.INFO)


class TestAuth0(object):
    def test_auth0_convert(self):
        az_data = {}
        with open("tests/fixture/auth0_users.json") as fd:
            az_data = json.load(fd)

        az = cis_publisher.auth0.Auth0Publisher()
        profiles = az.convert_az_users(az_data)

        print("Parsed {} profiles".format(len(profiles)))
        assert profiles[1].user_id.value == "email|dnoble"
