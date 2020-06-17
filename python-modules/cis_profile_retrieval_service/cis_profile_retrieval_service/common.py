import boto3
import botocore
import json
import logging
import os
import re
from botocore.stub import Stubber
from everett.ext.inifile import ConfigIniEnv
from everett.manager import ConfigManager
from everett.manager import ConfigOSEnv
from json import dumps
from cis_profile.fake_profile import batch_create_fake_profiles
from cis_identity_vault.models import user
from cis_identity_vault.vault import IdentityVault
from cis_profile.common import DisplayLevel
from cis_profile.common import MozillaDataClassification


logger = logging.getLogger(__name__)


def get_config():
    return ConfigManager(
        [ConfigIniEnv([os.environ.get("CIS_CONFIG_INI"), "~/.mozilla-cis.ini", "/etc/mozilla-cis.ini"]), ConfigOSEnv()]
    )


config = get_config()


def get_table_resource():
    region = config("dynamodb_region", namespace="cis", default="us-west-2")
    environment = config("environment", namespace="cis", default="local")
    table_name = "{}-identity-vault".format(environment)
    client_config = botocore.config.Config(max_pool_connections=50)

    if environment == "local":
        dynalite_host = config("dynalite_host", namespace="cis", default="localhost")
        dynalite_port = config("dynalite_port", namespace="cis", default="4567")
        session = Stubber(boto3.session.Session(region_name=region)).client
        resource = session.resource("dynamodb", endpoint_url="http://{}:{}".format(dynalite_host, dynalite_port))
    else:
        session = boto3.session.Session(region_name=region)
        resource = session.resource("dynamodb", config=client_config)

    table = resource.Table(table_name)
    return table


def get_dynamodb_client():
    region = config("dynamodb_region", namespace="cis", default="us-west-2")
    environment = config("environment", namespace="cis", default="local")
    client_config = botocore.config.Config(max_pool_connections=50)

    if environment == "local":
        dynalite_host = config("dynalite_host", namespace="cis", default="localhost")
        dynalite_port = config("dynalite_port", namespace="cis", default="4567")
        session = Stubber(boto3.session.Session(region_name=region)).client
        client = session.client(
            "dynamodb", endpoint_url="http://{}:{}".format(dynalite_host, dynalite_port), config=client_config
        )
    else:
        session = boto3.session.Session(region_name=region)
        client = session.client("dynamodb", config=client_config)

    return client


def initialize_vault():
    if config("environment", namespace="cis", default="local") == "local":
        identity_vault = IdentityVault()
        identity_vault.connect()
        identity_vault.find_or_create()
    else:
        return None


def seed(number_of_fake_users=100):
    seed_data = config("seed_api_data", namespace="cis", default="false")
    if seed_data.lower() == "true":
        table = get_table_resource()
        user_profile = user.Profile(table, None, False)

        if len(user_profile.all) > 0:
            logger.info("Identity vault is already seeded.  Passing on the additiona of users.")
            pass
        else:
            logger.info("Beginning the creation of seed users.")
            identities = batch_create_fake_profiles(1337, number_of_fake_users)

            for identity in identities:
                identity["pronouns"]["metadata"]["display"] = None
                identity_vault_data_structure = {
                    "id": identity.get("user_id").get("value"),
                    "primary_email": identity.get("primary_email").get("value"),
                    "user_uuid": identity.get("uuid").get("value"),
                    "primary_username": identity.get("primary_username").get("value"),
                    "sequence_number": "1234567890",
                    "profile": dumps(identity),
                }

                user_profile.create(identity_vault_data_structure)

            identities = batch_create_fake_profiles(1337, 1)

            for identity in identities:
                identity["pronouns"]["metadata"]["display"] = None
                identity["active"]["value"] = False
                identity_vault_data_structure = {
                    "id": identity.get("user_id").get("value"),
                    "primary_email": identity.get("primary_email").get("value"),
                    "user_uuid": identity.get("uuid").get("value"),
                    "primary_username": identity.get("primary_username").get("value"),
                    "sequence_number": "1234567890",
                    "profile": dumps(identity),
                }
                user_profile.create(identity_vault_data_structure)
            logger.info("Count: {} seed users created.".format(number_of_fake_users))


def load_dirty_json(dirty_json):
    regex_replace = [
        (r"([ \{,:\[])(u)?'([^']+)'", r'\1"\3"'),
        (r" False([, \}\]])", r" false\1"),
        (r" True([, \}\]])", r" true\1"),
    ]
    for r, s in regex_replace:
        dirty_json = re.sub(r, s, dirty_json)
    clean_json = json.loads(dirty_json)
    return clean_json


def scope_to_display_level(scopes):
    display_levels = []
    if "display:all" in scopes:
        logger.debug("all display level in scope.")
        display_levels.append(DisplayLevel.NONE)
        display_levels.append(DisplayLevel.NULL)

    if "display:staff" in scopes:
        logger.debug("staff display level in scope.")
        display_levels.append(DisplayLevel.STAFF)

    if "display:ndaed" in scopes:
        logger.debug("ndaed display level in scope.")
        display_levels.append(DisplayLevel.NDAED)

    if "display:vouched" in scopes:
        logger.debug("vouched display level in scope.")
        display_levels.append(DisplayLevel.VOUCHED)

    if "display:authenticated" in scopes:
        logger.debug("authenticated display level in scope.")
        display_levels.append(DisplayLevel.AUTHENTICATED)

    if "display:none" in scopes:
        logger.debug("None/NULL display level in scope.")
        display_levels.append(DisplayLevel.NULL)

    display_levels.append(DisplayLevel.PUBLIC)
    return display_levels


def scope_to_mozilla_data_classification(scopes):
    classifications = []
    if "classification:mozilla_confidential" in scopes:
        logger.debug("Mozilla confidential data classification in scope.")
        classifications.extend(MozillaDataClassification.MOZILLA_CONFIDENTIAL)

    if "classification:workgroup:staff_only" in scopes:
        logger.debug("Workgroup: staff only data classification in scope.")
        classifications.extend(MozillaDataClassification.STAFF_ONLY)

    if "classification:workgroup" in scopes:
        logger.debug("Workgroup data classification in scope.")
        classifications.extend(MozillaDataClassification.WORKGROUP_CONFIDENTIAL)

    if "classification:individual" in scopes:
        logger.debug("Individual data classification in scope.")
        classifications.extend(MozillaDataClassification.INDIVIDUAL_CONFIDENTIAL)

    classifications.extend(MozillaDataClassification.PUBLIC)
    return classifications


class DisplayLevelParms(object):
    public = [DisplayLevel.PUBLIC]
    authenticated = [DisplayLevel.PUBLIC, DisplayLevel.AUTHENTICATED]
    vouched = [DisplayLevel.PUBLIC, DisplayLevel.AUTHENTICATED, DisplayLevel.VOUCHED]
    ndaed = [DisplayLevel.PUBLIC, DisplayLevel.AUTHENTICATED, DisplayLevel.VOUCHED, DisplayLevel.NDAED]
    staff = [
        DisplayLevel.PUBLIC,
        DisplayLevel.AUTHENTICATED,
        DisplayLevel.VOUCHED,
        DisplayLevel.NDAED,
        DisplayLevel.STAFF,
    ]
    private = [
        DisplayLevel.PUBLIC,
        DisplayLevel.AUTHENTICATED,
        DisplayLevel.VOUCHED,
        DisplayLevel.NDAED,
        DisplayLevel.STAFF,
        DisplayLevel.PRIVATE,
    ]

    @classmethod
    def map(cls, display_level):
        return getattr(cls, display_level, cls.public)
