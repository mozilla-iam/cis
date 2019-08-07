import cis_profile
import cis_publisher
import boto3
import botocore
import os
import logging
import json
import time
import requests
from auth0.v3.authentication import GetToken
from auth0.v3.management import Auth0
from datetime import datetime, timezone, timedelta
from traceback import format_exc

logger = logging.getLogger(__name__)


class Auth0Publisher:
    def __init__(self, context={}):
        self.secret_manager = cis_publisher.secret.Manager()
        self.context = context
        self.report = None
        self.config = cis_publisher.common.get_config()
        # Only fields we care about for the user entries
        # auth0 field->cis field map
        self.az_cis_fields = {
            "created_at": "created",
            "updated_at": "last_modified",
            "given_name": "first_name",
            "family_name": "last_name",
            "name": None,
            "nickname": None,
            "picture": "picture",
            "user_id": "user_id",
            "email": "primary_email",
        }

    def publish(self, user_ids=None, chunk_size=30):
        """
        Glue to create or fetch cis_profile.User profiles for this publisher
        Then pass everything over to the Publisher class
        None, ALL profiles are sent.
        @user_ids: list of str - user ids to publish. If None, all users are published.
        @chunk_size: int when no user_id is selected, this is the size of the chunk/slice we'll create to divide the
        work between function calls (to self)
        """
        if user_ids is None:
            le = "All"
        else:
            le = len(user_ids)
        logger.info("Starting Auth0 Publisher [{} users]".format(le))

        # Should we fan-out processing to multiple function calls?
        if user_ids is None:
            self.fan_out(publisher, chunk_size)
        else:
            self.process(publisher, user_ids)

    def fetch_az_users(self, user_ids=[]):
        """
        Fetches ALL valid users from auth0'z database
        Returns list of user attributes
        """
        az_api_url = self.config("auth0_api_url", namespace="cis", default="auth-dev.mozilla.auth0.com")
        az_client_id = (self.secret_manager.secret("client_id"),)
        az_client_secret = (self.secret_manager.secret("client_secret"),)
        az_fields = self.az_cis_fields.keys()

        # Build the connection query (excludes LDAP)
        az_blacklist_connections = ["Mozilla-LDAP", "Mozilla-LDAP-Dev"]
        # Ignore non-verified `email` (such as unfinished passwordless flows) as we don't consider these to be valid
        # users
        az_query = "email_verified:true AND NOT ("
        t = ""
        for azc in az_connections:
            az_query = azquery + t + 'identities.connection:"{}"'.format(az_connections)
            t = " OR "
        az_query = az_query + ")"

        # Build query for user_ids if some are specified (else it gets all of them)
        if user_ids:
            logger.info("Restriction auth0 user query to user_ids: {}".format(user_ids))
            t = ""
            az_query = az_query + "AND ("
            for u in user_ids:
                az_query = az_query + t + 'user_id:"{}"'.format(u)
                t = " OR "
            az_query = az_query + ")"

        logger.debug("About to get Auth0 user list")
        az_getter = GetToken(az_api_url)
        az_token = az_getter.client_credentials(as_client_id, az_client_secret, "https://{}/api/v2/".format(az_api_url))
        auth0 = Auth0(az_api_url, az_token["access_token"])

        # Query the entire thing
        p = 0
        user_list = []
        # This is an artificial upper limit of 100*99999 (per_page*page) i.e. 9 999 900 users max - just in case things
        # go wrong
        for p in range(0, 99999):
            tmp = auth0.users.list(page=p, per_page=100, fields=az_fields, q=az_query)
            if tmp == []:
                # stop when our page is empty
                logger.debug("Crawled {} pages from auth0 users API".format(p))
                break
            else:
                user_list.extend(tmp)
        logger.info("Received {} users from auth0".format(len(user_list)))
        return user_list

    def convert_az_users(self, az_users):
        """
        Convert a list of auth0 user fields to cis_profile Users
        @az_users list of dicts with user attributes
        Returns [cis_profile.Users]
        """
        profiles = []
        for u in az_users:
            p = cis_profile.User()
            for k, v in self.az_cis_fields.items():
                if k not in u.keys():
                    continue
                p.__dict__[v]["value"] = u[k]

            # Hack:
            # In case no names were passed, try to fix things up with what we have
            if p.__dict__["first_name"]["value"] is None:
                logger.debug("User {} has no name, asserting a name from other values".format(u["user_id"]))
                if "name" in u.keys():
                    p.__dict__["first_name"]["value"] = u["name"]
                elif "nickname" in u.keys():
                    p.__dict__["first_name"]["value"] = u["nickname"]
                else:
                    p.__dict__["first_name"]["value"] = u["email"].split("@")[0]
            profiles.append(p)
        return profiles

    def process(self, publisher, user_ids):
        """
        Process profiles and post them
        @publisher object the publisher object to operate on
        @user_ids list of user ids to process in this batch
        """

        profiles = self.convert_az_users(self.fetch_az_users(user_ids))
        logger.info("Processing {} profiles".format(len(profiles)))
        publisher.profiles = profiles

        failures = []
        try:
            failures = publisher.post_all(user_ids=user_ids)
        except Exception as e:
            logger.error("Failed to post_all() profiles. Trace: {}".format(format_exc()))
            raise e

        if len(failures) > 0:
            logger.error("Failed to post {} profiles: {}".format(len(failures), failures))

    def fan_out(self, publisher, chunk_size):
        """
        Splices all users to process into chunks
        and self-invoke as many times as needed to complete all work in parallel lambda functions
        When self-invoking, this will effectively call self.process() instead of self.fan_out()
"]
        Note: chunk_size should never result in the invoke() argument to exceed 128KB (len(Payload.encode('utf-8') <
        128KB) as this is the maximum AWS Lambda payload size.

        @publisher object the cis_publisher object to operate on
        @chunk_size int size of the chunk to process
        """
        all_user_ids = []
        sliced = [all_user_ids[i : i + chunk_size] for i in range(0, len(all_user_ids), chunk_size)]
        logger.info(
            "No user_id selected. Creating slices of work, chunck size: {}, slices: {}, total users: {} and "
            "faning-out work to self".format(chunk_size, len(sliced), len(all_user_ids))
        )
        lambda_client = boto3.client("lambda")
        for s in sliced:
            lambda_client.invoke(FunctionName=self.context.function_name, InvocationType="Event", Payload=json.dumps(s))
            time.sleep(3)  # give api calls a chance, otherwise this storms resources

        logger.info("Exiting slicing function successfully")
