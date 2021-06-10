import boto3
import logging
import os
import random
import string
import cis_crypto
from cis_profile import common
from cis_profile import profile


logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("botocore").setLevel(logging.CRITICAL)
logging.getLogger("cis_crypto").setLevel(logging.CRITICAL)


class Configuration(object):
    def __init__(self):
        self.client = None
        self.keys = {}

    def get_cis_environment(self):
        return os.getenv("CIS_ENVIRONMENT", "development")

    def get_client_id_path(self):
        return "/iam/cis/{}/change_client_id".format(self.get_cis_environment())

    def get_client_secret_path(self):
        return "/iam/cis/{}/change_service_client_secret".format(self.get_cis_environment())

    def get_url_dict(self):
        cis_environment = self.get_cis_environment()

        if cis_environment == "development":
            change_url = "change.api.dev.sso.allizom.org"
            person_url = "person.api.dev.sso.allizom.org"
            audience = "api.dev.sso.allizom.org"

        if cis_environment == "testing":
            change_url = "change.api.test.sso.allizom.org"
            person_url = "person.api.test.sso.allizom.org"
            audience = "api.test.sso.allizom.org"

        if cis_environment == "production":
            change_url = "change.api.sso.allizom.org"
            person_url = "person.api.sso.allizom.org"
            audience = "api.sso.allizom.org"

        return dict(change=change_url, person=person_url, audience=audience)

    def get_secure_parameter(self, parameter_name):
        """Gets the desired secret for secureStrings only from AWS Parameter Store.

        Arguments:
            parameter_name {string} -- The name of the parameter not including the path
            to retrieve from parameter store.

        Returns:
            [type] -- string literal decrypted value.
        """

        if self.client is None:
            self.client = boto3.client("ssm")

        if self.keys.get(parameter_name):
            logger.info("Key is coming from object cache for: {}".format(parameter_name))
            return self.keys.get(parameter_name)
        else:
            logger.info("Key is not coming from object cache for: {}".format(parameter_name))
            response = self.client.get_parameter(Name=parameter_name, WithDecryption=True)
            self.keys[parameter_name] = response["Parameter"]["Value"]
            return response["Parameter"]["Value"]

    def get_client_secret(self):
        return self.get_secure_parameter(self.get_client_secret_path())

    def get_client_id(self):
        return self.get_secure_parameter(self.get_client_id_path())

    def get_complex_structures(self):
        return ["staff_information", "access_information", "identities", "schema"]

    def ensure_appropriate_publishers_and_sign(self, fake_profile, condition):
        """Workaround the fact the FakerUser generator does not always generate valid profiles.
        Iterates over the attributes and ensures the profile will pass publisher rule validation.

        Arguments:
            fake_profile {object} -- A fake user object of cis_profile.profile.User() type.
            condition {string} -- Takes update for create as a condition.

        Returns:
            [type] -- A user object of type cis_profile.profile.User() with valid publishers and signatures.
        """

        os.environ["CIS_SECRET_MANAGER"] = "aws-ssm"
        os.environ["CIS_SECRET_MANAGER_SSM_PATH"] = "/iam/cis/{env}/keys".format(
            env=os.getenv("CIS_ENVIRONMENT", "development")
        )

        publisher_rules = common.WellKnown().get_publisher_rules()
        complex_structures = self.get_complex_structures()

        temp_profile = fake_profile.as_dict()
        for attr in publisher_rules[condition]:
            if attr == "primary_username" and temp_profile[attr]["value"] == "None":
                temp_profile[attr]["value"] = "".join(
                    [random.choice(string.ascii_letters + string.digits) for n in xrange(32)]
                )

            if attr not in complex_structures:
                successful_random_publisher = random.choice(publisher_rules[condition][attr])
                temp_profile[attr]["signature"]["publisher"]["name"] = successful_random_publisher
                self.u = profile.User(user_structure_json=temp_profile)
                # Don't sign NULL attributes or invalid publishers
                if self.u._attribute_value_set(temp_profile[attr], strict=True) and (
                    temp_profile[attr]["signature"]["publisher"]["name"] == successful_random_publisher
                ):
                    self.u.sign_attribute(attr, successful_random_publisher)
                    logger.info("Signing attr: {}".format(attr))
                temp_profile = self.u.as_dict()
            else:
                if attr != "schema" and attr in complex_structures:
                    for k in temp_profile[attr]:
                        successful_random_publisher = random.choice(publisher_rules[condition][attr][k])

                        temp_profile[attr][k]["signature"]["publisher"]["name"] = successful_random_publisher
                        self.u = profile.User(user_structure_json=temp_profile)

                        attribute = "{}.{}".format(attr, k)
                        # Don't sign NULL attributes or invalid publishers
                        if self.u._attribute_value_set(temp_profile[attr][k], strict=True) and (
                            temp_profile[attr][k]["signature"]["publisher"]["name"] == successful_random_publisher
                        ):
                            self.u.sign_attribute(attribute, successful_random_publisher)
                        temp_profile = self.u.as_dict()

        return profile.User(user_structure_json=temp_profile)
