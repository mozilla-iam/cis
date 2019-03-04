"""Get the status of an integration from the identity vault and auth0."""
import json
import logging
import uuid
from botocore.exceptions import ClientError
from cis_aws import connect
from cis_change_service import common
from cis_identity_vault.models import user
from cis_profile.profile import User
from cis_change_service.exceptions import IntegrationError
from cis_change_service.exceptions import VerificationError
from cis_profile.exceptions import PublisherVerificationFailure
from cis_profile.exceptions import SignatureVerificationFailure
from traceback import format_exc


logger = logging.getLogger(__name__)


class Vault(object):
    """Handles flushing profiles to Dynamo when running local or in stream bypass mode."""

    def __init__(self, sequence_number=None):
        self.connection_object = connect.AWS()
        self.identity_vault_client = None
        self.config = common.get_config()
        self.condition = "unknown"

        if sequence_number is not None:
            self.sequence_number = str(sequence_number)
        else:
            self.sequence_number = str(uuid.uuid4().int)

    def _connect(self):
        self.connection_object.session()
        self.identity_vault_client = self.connection_object.identity_vault_client()
        return self.identity_vault_client

    def _verify(self, profile_json, old_profile=None):
        cis_profile_object = User(user_structure_json=profile_json)
        user_id = cis_profile_object.as_dict()["user_id"].get("value", "")

        try:
            if self.config("verify_publishers", namespace="cis") == "true":
                logger.info("Verifying publishers.")
                user = self._search_and_merge(cis_profile_object)
                cis_profile_object.verify_all_publishers(user)
            else:
                # Search for the user without verification to set condition.
                user = self._search_and_merge(cis_profile_object)

            if self.config("verify_signatures", namespace="cis") == "true":
                user.verify_all_signatures()
        except SignatureVerificationFailure as e:
            logger.error(
                "The profile failed to pass signature verification for user: {}".format(user_id),
                extra={"user_id": user_id, "profile": user.as_dict(), "reason": e, "trace": format_exc()},
            )

            raise VerificationError({"code": "invalid_signature", "description": "{}".format(e)}, 403)
        except PublisherVerificationFailure as e:
            logger.error(
                "The profile failed to pass publisher verification for user: {}".format(user_id),
                extra={"user_id": user_id, "profile": user.as_dict(), "reason": e, "trace": format_exc()},
            )
            raise VerificationError({"code": "invalid_publisher", "description": "{}".format(e)}, 403)
        except Exception as e:
            logger.error(
                "The profile produced an unknown error and is not trusted for user: {}".format(user_id),
                extra={"user_id": user_id, "profile": cis_profile_object.as_dict(), "reason": e, "trace": format_exc()},
            )
            logger.error("The error causing a trust problem is: {}".format(e))
            raise VerificationError({"code": "unknown_error", "description": "{}".format(e)}, 500)
        return user

    def _update_attr_owned_by_cis(self, profile_json):
        """Updates the attributes owned by cisv2.  Takes profiles profile_json
        and returns a profile dict with updated values and sigs."""

        # New up a a cis_profile object
        user = User(user_structure_json=profile_json)
        user.update_timestamp("last_modified")
        user.last_modified.value = user._get_current_utc_time()
        user.sign_attribute("last_modified", "cis")

        # Currently we accept LDAP and Auth0 disabling a user
        # but since CIS is authoritative on this attribute, we rewrite it here
        # XXX THIS IS AN EXCEPTION AND SHOULD BE REMOVED WHEN ONLY HRIS CAN DISABLE USERS
        # A separate scope/endpoint should be made available to disable+delete users on demand, that isn't using their
        # publishers
        if user.active.signature.publisher.name in ["ldap", "access_provider", "hris"]:
            if self.config("verify_signatures", namespace="cis") == "true":
                user.verify_attribute_signature("active")
            user.sign_attribute("active", "cis")
        # XXX this should probably return a User object (and have a self.user in the class) instead
        return user.as_dict()

    def _search_and_merge(self, cis_profile_object):
        self._connect()

        user_id = cis_profile_object.user_id.value

        logger.info("Attempting to locate user: {}".format(user_id))
        vault = user.Profile(self.identity_vault_client.get("table"), self.identity_vault_client.get("client"))

        try:
            res = vault.find_by_id(user_id)
            logger.info("The result of the search contained: {}".format(len(res["Items"])))
        except Exception as e:
            logger.error("Problem finding user profile in identity vault due to: {}".format(e))
            res = {"Items": [0]}

        if len(res["Items"]) > 0:
            self.condition = "update"
            logger.info(
                "A record already exists in the identity vault for user: {}.".format(user_id),
                extra={"user_id": user_id},
            )

            old_user_profile = User(user_structure_json=json.loads(res["Items"][0]["profile"]))
            old_user_profile.merge(cis_profile_object)
            return old_user_profile
        else:
            self.condition = "create"
            logger.info(
                "A record does not exist in the identity vault for user: {}.".format(user_id),
                extra={"user_id": user_id},
            )
            return User()

    def put_profile(self, profile_json):
        """Write profile to the identity vault."""
        try:
            self._connect()

            # XXX Hey its not JSON anymore then.
            if isinstance(profile_json, str):
                profile_json = json.loads(profile_json)

            # Run some code that updates attrs and metadata for attributes cis is trusted to assert
            profile_json = self._verify(profile_json).as_dict()
            profile_json = self._update_attr_owned_by_cis(profile_json)

            if self.config("dynamodb_transactions", namespace="cis") == "true":
                vault = user.Profile(
                    self.identity_vault_client.get("table"), self.identity_vault_client.get("client"), transactions=True
                )
            else:
                vault = user.Profile(
                    self.identity_vault_client.get("table"),
                    self.identity_vault_client.get("client"),
                    transactions=False,
                )

            user_profile = dict(
                id=profile_json["user_id"]["value"],
                primary_email=profile_json["primary_email"]["value"],
                user_uuid=profile_json["uuid"]["value"],
                primary_username=profile_json["primary_username"]["value"],
                sequence_number=self.sequence_number,
                profile=json.dumps(profile_json),
            )

            res = vault.find_or_create(user_profile)
            logger.info(
                "The result of writing the profile to the identity vault was: {}".format(res),
                extra={"user_id": profile_json["user_id"]["value"], "profile": profile_json, "result": res},
            )

            return dict(sequence_number=self.sequence_number, status_code=200, condition=self.condition)
        except ClientError as e:
            logger.error(
                "An error occured writing this profile to dynamodb",
                extra={"profile": profile_json, "error": e, "trace": format_exc()},
            )
            logger.error("The error blocking write is: {}".format(e))
            raise IntegrationError({"code": "integration_exception", "description": "{}".format(e)}, 500)

    def put_profiles(self, profile_list):
        """Write profile to the identity vault."""
        try:
            self._connect()

            if self.config("dynamodb_transactions", namespace="cis") == "true":
                logger.debug("Attempting to put batch of profiles using transactions.")
                vault = user.Profile(
                    self.identity_vault_client.get("table"), self.identity_vault_client.get("client"), transactions=True
                )
            else:
                logger.info("Attempting to put batch of profiles without transactions.")
                vault = user.Profile(
                    self.identity_vault_client.get("table"),
                    self.identity_vault_client.get("client"),
                    transactions=False,
                )

            user_profiles = []

            for profile_json in profile_list:
                if isinstance(profile_json, str):
                    profile_json = json.loads(profile_json)

                # Run some code that updates attrs and metadata for attributes cis is trusted to assert
                verified = self._verify(profile_json)
                profile_json = self._update_attr_owned_by_cis(profile_json)
                if verified:
                    logger.debug("Profiles have been verified. Constructing dictionary for storage.")
                    user_profile = dict(
                        id=profile_json["user_id"]["value"],
                        primary_email=profile_json["primary_email"]["value"],
                        user_uuid=profile_json["uuid"]["value"],
                        primary_username=profile_json["primary_username"]["value"],
                        sequence_number=self.sequence_number,
                        profile=json.dumps(profile_json),
                    )
                    user_profiles.append(user_profile)

            logger.debug(
                "Attempting to send a list numbering: {} profiles as a transaction.".format(len(user_profiles))
            )
            result = vault.find_or_create_batch(user_profiles)
        except ClientError as e:
            logger.error(
                "An error occured writing these profiles to dynamodb",
                extra={"profiles": profile_list, "error": e, "trace": format_exc()},
            )
            raise IntegrationError({"code": "integration_exception", "description": "{}".format(e)}, 500)
        return {"creates": result[0], "updates": result[1]}

    def delete_profile(self, profile_json):
        condition = "delete"
        try:
            user_profile = dict(
                id=profile_json["user_id"]["value"],
                primary_email=profile_json["primary_email"]["value"],
                user_uuid=profile_json["uuid"]["value"],
                primary_username=profile_json["primary_username"]["value"],
                sequence_number=self.sequence_number,
                profile=json.dumps(profile_json),
            )

            if self.config("dynamodb_transactions", namespace="cis") == "true":
                logger.debug("Attempting to put batch of profiles using transactions.")
                vault = user.Profile(
                    self.identity_vault_client.get("table"), self.identity_vault_client.get("client"), transactions=True
                )
            else:
                logger.info("Attempting to put batch of profiles without transactions.")
                vault = user.Profile(
                    self.identity_vault_client.get("table"),
                    self.identity_vault_client.get("client"),
                    transactions=False,
                )

            vault.delete(user_profile)
        except ClientError as e:
            logger.error(
                "An error occured removing this profile from dynamodb",
                extra={"profile": profile_json, "error": e, "trace": format_exc()},
            )
            raise IntegrationError({"code": "integration_exception", "description": "{}".format(e)}, 500)
        return {
            "status": 200,
            "message": "user profile deleted for user: {}".format(profile_json["user_id"]["value"]),
            "condition": condition,
        }

    def _get_id(self, profile_json):
        if isinstance(profile_json, str):
            profile_json = json.loads(profile_json)
        return profile_json.get("user_id").get("value").lower()

    def _get_primary_email(self, profile_json):
        if isinstance(profile_json, str):
            profile_json = json.loads(profile_json)
        return profile_json.get("primary_email").get("value").lower()


class Status(object):
    """Does the right thing to query if the event was integrated and return the results."""

    def __init__(self, sequence_number):
        self.connection_object = connect.AWS()
        self.identity_vault_client = None
        self.sequence_number = sequence_number

    def _connect(self):
        self.connection_object.session()
        self.identity_vault_client = self.connection_object.identity_vault_client()
        return self.identity_vault_client

    def query(self):
        """Query the identity vault using the named Global Secondary Index for the sequence number."""
        # Vault returns a dictionary of dictionaries for the statuses of each check.
        self._connect()

        client = self.identity_vault_client.get("client")

        result = client.query(
            TableName=self.identity_vault_client.get("arn").split("/")[1],
            IndexName="{}-sequence_number".format(self.identity_vault_client.get("arn").split("/")[1]),
            Select="ALL_ATTRIBUTES",
            KeyConditionExpression="sequence_number = :sequence_number",
            ExpressionAttributeValues={":sequence_number": {"S": self.sequence_number}},
        )

        return result

    @property
    def all(self):
        """Run all checks and return the results for the given sequence number as a dict."""
        return {"identity_vault": self.check_identity_vault()}

    def check_identity_vault(self):
        """Check the sequence number of the last record put to the identity vault."""
        if self.identity_vault_client is None:
            self._connect()

        query_result = self.query()
        if len(query_result.get("Items")) == 1:
            return True
        else:
            return False
