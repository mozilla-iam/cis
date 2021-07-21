"""Designed to run against the testing environment."""
import boto3
import logging
import os

from cis_identity_vault.models import user


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('boto3').setLevel(logging.CRITICAL)
logging.getLogger('botocore').setLevel(logging.CRITICAL)

dynamodb_client = boto3.client("dynamodb")
dynamodb_table = boto3.resource("dynamodb").Table("testing-identity-vault")


def setup_environment():
    os.environ["CIS_ENVIRONMENT"] = "testing"
    os.environ["CIS_REGION_NAME"] = "us-west-2"
    os.environ["DEFAULT_AWS_REGION"] = "us-west-2"


def filtered_scan_wrapper():
    setup_environment()
    u = user.Profile(
        dynamodb_table_resource=dynamodb_table,
        dynamodb_client=dynamodb_client, transactions=True
    )
    connection_methods = ["github", "ad", "email", "oauth2", "google-oauth2"]
    results = []

    for conn_method in connection_methods:
        result = u.all_filtered(connection_method=conn_method, active=True, next_page=None)

        results.extend(result["users"])

        while result.get("nextPage"):
            logger.info("Trying to follow the page.")
            logger.info("Next page currently is: {}".format(result.get("nextPage")))
            result = u.all_filtered(connection_method=conn_method, active=True, next_page=result.get("nextPage"))
            results.extend(result["users"])
            logger.debug("Total records retrieved: {}".format(len(results)))

    logger.debug("Total records retrieved: {}".format(len(results)))


def filtered_scan_wrapper_inactive():
    setup_environment()
    u = user.Profile(
        dynamodb_table_resource=dynamodb_table,
        dynamodb_client=dynamodb_client, transactions=True
    )

    results = []
    result = u.all_filtered(connection_method="ad")

    results.extend(result["users"])

    while result.get("nextPage"):
        result = u.all_filtered(connection_method="ad", next_page=result.get("nextPage"), active=False)
        results.extend(result["users"])
        logger.debug("Total records retrieved: {}".format(len(results)))

    logger.debug("Total records retrieved: {}".format(len(results)))


def test_filtered_scan(benchmark):
    benchmark.pedantic(filtered_scan_wrapper, iterations=1, rounds=1)


def test_filtered_scan_inactive(benchmark):
    benchmark.pedantic(filtered_scan_wrapper_inactive, iterations=1, rounds=1)
