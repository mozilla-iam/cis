"""Designed to run against the testing environment."""
import boto3
import logging
import os
import pytest

from cis_identity_vault.models import user


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
logging.getLogger('boto3').setLevel(logging.CRITICAL)
logging.getLogger('botocore').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)


def setup_environment():
    os.environ["CIS_ENVIRONMENT"] = "testing"
    os.environ["CIS_REGION_NAME"] = "us-west-2"
    os.environ["AWS_DEFAULT_REGION"] = "us-west-2"


def get_all_by_page():
    setup_environment()
    u = user.Profile(
        dynamodb_table_resource=boto3.resource("dynamodb").Table("testing-identity-vault"),
        dynamodb_client=boto3.client("dynamodb"), transactions=True
    )
    results = []

    result = u.all_by_page()

    results.extend(result["Items"])

    print(len(results))
    for x in range(0, 5):
        logger.info("Trying to follow the page.")
        logger.info("Next page currently is: {}".format(result.get("LastEvaluatedKey")))
        result = u.all_by_page(next_page=result.get("LastEvaluatedKey"))
        results.extend(result["Items"])
        logger.debug("Total records retrieved: {}".format(len(results)))

    logger.debug("Total records retrieved: {}".format(len(results)))


def get_all_by_any():
    setup_environment()
    u = user.Profile(
        dynamodb_table_resource=boto3.resource("dynamodb").Table("testing-identity-vault"),
        dynamodb_client=boto3.client("dynamodb"), transactions=True
    )
    results = []
    pages = []

    result = u.find_by_any(
        attr="staff_information.director", comparator=True, full_profiles=False
    )

    results.extend(result["users"])

    while result.get('nextPage'):
        if result.get('nextPage') in pages:
            break

        pages.append(result.get('nextPage'))
        logger.info("Trying to follow the page.")
        logger.info("Next page currently is: {}".format(result.get("nextPage")))
        result = u.find_by_any(attr="staff_information.staff", comparator=True, next_page=result.get("nextPage"))
        results.extend(result["users"])
        logger.info("Total records retrieved: {}".format(len(results)))
    logger.info("Total records retrieved: {}".format(len(results)))


@pytest.mark.skip(reason="Bit rot (boto).")
def test_filtered_scan(benchmark):
    # get_all_by_any()
    benchmark.pedantic(get_all_by_any, iterations=1, rounds=1)
