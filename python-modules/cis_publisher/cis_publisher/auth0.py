import cis_profile
import cis_publisher
import boto3
import botocore
import os
import logging
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from traceback import format_exc

logger = logging.getLogger(__name__)


class Auth0Publisher:
    def __init__(self, context={}):
        self.secret_manager = cis_publisher.secret.Manager()
        self.context = context
        self.report = None

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

    def process(self, publisher, user_ids):
        """
        Process profiles and post them
        @publisher object the publisher object to operate on
        @user_ids list of user ids to process in this batch
        """
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
