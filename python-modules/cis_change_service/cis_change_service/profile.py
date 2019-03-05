"""Get the status of an integration from the identity vault and auth0."""
import json
import logging
import uuid
import copy
import cis_profile
from botocore.exceptions import ClientError
from cis_aws import connect
from cis_change_service import common
from cis_identity_vault.models import user
from cis_profile.profile import User
from cis_change_service.exceptions import IntegrationError
from cis_change_service.exceptions import VerificationError
from traceback import format_exc


logger = logging.getLogger(__name__)


class Vault(object):
    """Handles flushing profiles to Dynamo when running local or in stream bypass mode."""

    def __init__(self, sequence_number=None, profile_json=None, **kwargs):
        self.connection_object = connect.AWS()
        self.identity_vault_client = None
        self.config = common.get_config()
        self.condition = "unknown"
        self.user_id = kwargs.get("user_id")
        self.user_uuid = kwargs.get("user_uuid")
        self.primary_email = kwargs.get("primary_email")
        self.primary_username = kwargs.get("primary_username")

        if self.user_id is None:
            logger.info("No user_id arg was passed for the payload. This is a new user or batch.")
            tmp_user = User(user_structure_json=profile_json)
            self.user_id = tmp_user.user_id.value
            self.condition = "create"

        if sequence_number is not None:
            self.sequence_number = str(sequence_number)
        else:
            self.sequence_number = str(uuid.uuid4().int)

    def _connect(self):
        """
        Connect to the vault
        """
        self.connection_object.session()
        self.identity_vault_client = self.connection_object.identity_vault_client()
        return self.identity_vault_client

    def _update_attr_owned_by_cis(self, user_id, user):
        """
        Updates the attributes owned by CIS itself. Updated attributes:
        - last_modified
        - active (XXX to be removed in the future, see comments below)

        @user_id str of the user's user_id
        @user a cis_profile.User object to update the attributes of

        Returns a cis_profile.User object with updated, signed values
        """

        logger.info("Updating CIS owned attributes", extra={"user_id": user_id})
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
                logger.info("Verifying signature of attribute active", extra={"user_id": user_id})
                user.verify_attribute_signature("active")
            else:
                logger.warning(
                    "Verifying CIS owned signatures bypassed due to setting `verify_signatures` being false",
                    extra={"user_id": user_id},
                )
            user.sign_attribute("active", "cis")

        # Re-verifying signatures for consistency, since we modified them
        if self.config("verify_signatures", namespace="cis") == "true":
            user.verify_attribute_signature("active")
            user.verify_attribute_signature("last_modified")
        else:
            logger.warning(
                "Verifying CIS owned signatures bypassed due to setting `verify_signatures` being false",
                extra={"user_id": user_id},
            )

        return user

    def _search_and_merge(self, user_id, cis_profile_object):
        """
        Search for an existing user in the vault for the given profile
        If one exist, merge the given profile with the existing user
        If not, return the given profile

        WARNING: This function also verifies the publishers are valid, as this verification requires knowledge of the
        incoming user profile, profile in the vault, and resulting merged profile.

        @cis_profile_object cis_profile.User object of an incoming user
        @user_id str the user id of cis_profile_object

        Returns a cis_profile.User object
        """

        try:
            self._connect()
            vault = user.Profile(self.identity_vault_client.get("table"), self.identity_vault_client.get("client"))
            res = vault.find_by_id(user_id)
            logger.info("Search user in vault results: {}".format(len(res["Items"])))

        except Exception as e:
            logger.error("Problem finding user profile in identity vault due to: {}".format(e))
            res = {"Items": []}

        if len(res["Items"]) > 0:
            # This profile exists in the vault and will be merged and it's publishers verified
            self.condition = "update"
            logger.info(
                "A record already exists in the identity vault for user: {}.".format(user_id),
                extra={"user_id": user_id},
            )

            old_user_profile = User(user_structure_json=json.loads(res["Items"][0]["profile"]))
            new_user_profile = copy.deepcopy(old_user_profile)
            new_user_profile.merge(cis_profile_object)
            if self.config("verify_publishers", namespace="cis") == "true":
                logger.info("Verifying publishers", extra={"user_id": user_id})
                try:
                    new_user_profile.verify_all_publishers(old_user_profile)
                except Exception as e:
                    logger.error(
                        "The merged profile failed to pass publisher verification",
                        extra={
                            "user_id": user_id,
                            "profile": new_user_profile.as_dict(),
                            "reason": e,
                            "trace": format_exc(),
                        },
                    )
                    raise VerificationError({"code": "invalid_publisher", "description": "{}".format(e)}, 403)
            else:
                logger.warning(
                    "Bypassing profile publisher verification due to `verify_publishers` setting being false",
                    extra={"user_id": user_id},
                )
            return new_user_profile
        else:
            # This profile as not merged, just verify publishers and return it
            self.condition = "create"
            logger.info(
                "A record does not exist in the identity vault for user: {}.".format(user_id),
                extra={"user_id": user_id},
            )
            if self.config("verify_publishers", namespace="cis") == "true":
                logger.info("Verifying publishers", extra={"user_id": user_id})
                try:
                    cis_profile_object.verify_all_publishers(cis_profile.User())
                except Exception as e:
                    logger.error(
                        "The profile failed to pass publisher verification",
                        extra={
                            "user_id": user_id,
                            "profile": cis_profile_object.as_dict(),
                            "reason": e,
                            "trace": format_exc(),
                        },
                    )
                    raise VerificationError({"code": "invalid_publisher", "description": "{}".format(e)}, 403)
            else:
                logger.warning(
                    "Bypassing profile publisher verification due to `verify_publishers` setting being false",
                    extra={"user_id": user_id},
                )
            return cis_profile_object

    def put_profile(self, _profile):
        """
        Wrapper for a single profile, calls the batch put_profiles method
        """
        res = self.put_profiles([_profile])
        if res["creates"] is not None and len(res["creates"]["sequence_numbers"]) == 1:
            sequence_number = res["creates"]["sequence_numbers"][0]
            condition = "create"
        elif res["updates"] is not None and len(res["updates"]["sequence_numbers"]) == 1:
            sequence_number = res["updates"]["sequence_numbers"][0]
            condition = "update"
        else:
            raise IntegrationError(
                {"code": "integration_exception", "description": "No operation occurred: {}".format(res)}, 500
            )

        return dict(sequence_number=sequence_number, status_code=res["status"], condition=condition)

    def put_profiles(self, profiles):
        """
        Merge profile data as necessary with existing profile data for a given user
        Verify profile data is correctly signed and published by allowed publishers
        Write back the result to the identity vault.
        @profiles list of str or cis_profile.User object

        Returns a dictionary containing vault results
        """

        # User profiles that have been verified, validated, merged, etc.
        profiles_to_store = []

        for user_profile in profiles:
            # Ensure we always have a cis_profile.User at this point (compat)
            if isinstance(user_profile, str):
                user_profile = cis_profile.User(user_structure_json=user_profile)
            elif isinstance(user_profile, dict):
                user_profile = cis_profile.User(user_structure_json=json.dumps(user_profile))

            # For single put_profile events the user_id is passed as argument
            if self.user_id:
                user_id = self.user_id
                # Verify that we're passing the same as the signed user_id for safety reasons
                if user_profile._attribute_value_set(user_profile.user_id) and (user_id != user_profile.user_id.value):
                    raise IntegrationError(
                        {
                            "code": "integration_exception",
                            "description": "user_id query parameter does not match profile, that looks wrong",
                        },
                        400,
                    )

            else:
                user_id = user_profile.user_id.value
            logger.info("Attempting integration of profile data into the vault", extra={"user_id": user_id})

            # Ensure we merge user_profile data when we have an existing user in the vault
            # This also does publisher verification
            current_user = self._search_and_merge(user_id, user_profile)

            # Check profile signatures
            if self.config("verify_signatures", namespace="cis") == "true":
                try:
                    current_user.verify_all_signatures()
                except Exception as e:
                    logger.error(
                        "The profile failed to pass signature verification for user_id: {}".format(user_id),
                        extra={
                            "user_id": user_id,
                            "profile": current_user.as_dict(),
                            "reason": e,
                            "trace": format_exc(),
                        },
                    )
                    raise VerificationError({"code": "invalid_signature", "description": "{}".format(e)}, 403)
            else:
                logger.warning("Bypassing profile signature verification (`verify_signatures` setting is false)")

            # Update any CIS-owned attributes
            current_user = self._update_attr_owned_by_cis(user_id, current_user)

            profiles_to_store.append(current_user)

        # Store resulting user in the vault
        logger.info("Will store {} verified profiles".format(len(profiles_to_store)))
        return self._store_in_vault(profiles_to_store)

    def _store_in_vault(self, profiles):
        """
        Actually store profiles in the vault
        All profiles must have been merged and verified correctly before calling this method

        @profiles list of cis_profiles.User

        Returns dict {"creates": result_of_users_created, "updates": result_of_users_updates}
        """

        # Vault profiles (not cis_profile.User objects)
        vault_profiles = []

        try:
            self._connect()

            if self.config("dynamodb_transactions", namespace="cis") == "true":
                logger.debug("Attempting to put batch of profiles ({}) using transactions.".format(len(profiles)))
                vault = user.Profile(
                    self.identity_vault_client.get("table"), self.identity_vault_client.get("client"), transactions=True
                )
            else:
                logger.debug(
                    "Attempting to put batch of profiles ({}) without using transactions.".format(len(profiles))
                )
                vault = user.Profile(
                    self.identity_vault_client.get("table"),
                    self.identity_vault_client.get("client"),
                    transactions=False,
                )

            # transform cis_profiles.User profiles to vault profiles
            for user_profile in profiles:
                vault_profile = dict(
                    id=user_profile.user_id.value,
                    primary_email=user_profile.primary_email.value,
                    user_uuid=user_profile.uuid.value,
                    primary_username=user_profile.primary_username.value,
                    sequence_number=self.sequence_number,
                    profile=user_profile.as_json(),
                )
                vault_profiles.append(vault_profile)

            result = vault.find_or_create_batch(vault_profiles)
        except ClientError as e:
            logger.error(
                "An error occured writing these profiles to dynamodb",
                extra={"profiles": profiles, "error": e, "trace": format_exc()},
            )
            raise IntegrationError({"code": "integration_exception", "description": "{}".format(e)}, 500)
        # The result looks something like this:
        # result = {'creates': {'status': '200',
        # 'sequence_numbers': ['285229813155718975995433494324446866394']}, 'updates': None, 'status': 200}"}
        return {"creates": result[0], "updates": result[1], "status": 200}

    def delete_profile(self, profile_json):
        # XXX This method should be refactored to look like put_profiles() / put_profile()
        self.condition = "delete"

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
            "condition": self.condition,
        }


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
