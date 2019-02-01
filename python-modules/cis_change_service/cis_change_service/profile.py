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


logger = logging.getLogger(__name__)


class Vault(object):
    """Handles flushing profiles to Dynamo when running local or in stream bypass mode."""

    def __init__(self, sequence_number=None):
        self.connection_object = connect.AWS()
        self.identity_vault_client = None
        self.config = common.get_config()

        if sequence_number is not None:
            self.sequence_number = str(sequence_number)
        else:
            self.sequence_number = str(uuid.uuid4().int)

    def _connect(self):
        self.connection_object.session()
        self.identity_vault_client = self.connection_object.identity_vault_client()
        return self.identity_vault_client

    def _verify(self, profile_json):
        cis_profile = User(user_structure_json=profile_json)
        user_id = cis_profile.user_id.value

        try:
            if self.config("verify_publishers", namespace="cis") == "true":
                cis_profile.verify_all_publishers(User())

            if self.config("verify_signatures", namespace="cis") == "true":
                cis_profile.verify_all_signatures()
        except SignatureVerificationFailure as e:
            logger.error(
                "The profile vailed to pass signature verification for user: {}".format(user_id),
                extra={"user_id": user_id, "profile": cis_profile.as_dict(), "reason": e},
            )

            raise VerificationError({"code": "invalid_signature", "description": "{}".format(e)}, 403)
        except PublisherVerificationFailure as e:
            logger.error(
                "The profile vailed to pass publisher verification for user: {}".format(user_id),
                extra={"user_id": user_id, "profile": cis_profile.as_dict(), "reason": e},
            )
            raise VerificationError({"code": "invalid_publisher", "description": "{}".format(e)}, 403)
        except Exception as e:
            logger.error(
                "The profile produced an unknown error and is not trusted for user: {}".format(user_id),
                extra={"user_id": user_id, "profile": cis_profile.as_dict(), "reason": e},
            )
            raise VerificationError({"code": "unknown_error", "description": "{}".format(e)}, 500)
        return True

    def _update_attr_owned_by_cis(self, profile_json):
        """Updates the attributes owned by cisv2.  Takes profiles profile_json
        and returns a profile json with updated values and sigs."""

        # New up a a cis_profile object
        user = User(user_structure_json=profile_json)
        user.update_timestamp("last_modified")
        user.last_modified.value = user._get_current_utc_time()
        user.sign_attribute("last_modified", "cis")

    def put_profile(self, profile_json):
        """Write profile to the identity vault."""
        try:
            self._connect()

            if isinstance(profile_json, str):
                profile_json = json.loads(profile_json)

            # Run some code that updates attrs and metadata for attributes cis is trusted to assert
            self._update_attr_owned_by_cis(profile_json)
            verified = self._verify(profile_json)

            if verified:
                if self.config("dynamodb_transactions", namespace="cis") == "true":
                    vault = user.Profile(
                        self.identity_vault_client.get("table"),
                        self.identity_vault_client.get("client"),
                        transactions=True,
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
                    uuid=profile_json["uuid"]["value"],
                    primary_username=profile_json["primary_username"]["value"],
                    sequence_number=self.sequence_number,
                    profile=json.dumps(profile_json),
                )

                res = vault.find_or_create(user_profile)
                logger.debug(
                    "The result of writing the profile to the identity vault was: {}".format(res),
                    extra={"user_id": profile_json["user_id"]["value"], "profile": profile_json, "result": res},
                )
                return res
        except ClientError as e:
            logger.error(
                "An error occured writing this profile to dynamodb", extra={"profile": profile_json, "error": e}
            )
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
                self._update_attr_owned_by_cis(profile_json)
                verified = self._verify(profile_json)
                if verified:
                    logger.debug("Profiles have been verified. Constructing dictionary for storage.")
                    user_profile = dict(
                        id=profile_json["user_id"]["value"],
                        primary_email=profile_json["primary_email"]["value"],
                        uuid=profile_json["uuid"]["value"],
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
                "An error occured writing these profiles to dynamodb", extra={"profiles": profile_list, "error": e}
            )
            raise IntegrationError({"code": "integration_exception", "description": "{}".format(e)}, 500)
        return {"creates": result[0], "updates": result[1]}

    def delete_profile(self, profile_json):
        try:
            user_profile = dict(
                id=profile_json["user_id"]["value"],
                primary_email=profile_json["primary_email"]["value"],
                uuid=profile_json["uuid"]["value"],
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
                "An error occured removing this profile from dynamodb", extra={"profile": profile_json, "error": e}
            )
            raise IntegrationError({"code": "integration_exception", "description": "{}".format(e)}, 500)
        return {"status": 200, "message": "user profile deleted for user: {}".format(profile_json["user_id"]["value"])}

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
