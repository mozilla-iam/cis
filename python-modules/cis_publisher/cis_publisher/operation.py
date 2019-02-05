"""Send a profile: full or partial to kinesis.  Report back stream entry status."""
import cis_profile
import http.client
import json
import jsonschema
import logging

from boto.kinesis.exceptions import ResourceNotFoundException
from boto.kinesis.exceptions import InvalidArgumentException
from cis_aws import connect
from cis_publisher.common import get_config
from urllib.parse import quote_plus


logger = logging.getLogger(__name__)


class Publish(object):
    def __init__(self):
        self.config = get_config()
        self.connection_object = connect.AWS()
        self.kinesis_client = None
        self.wk = cis_profile.common.WellKnown()
        self.schema = self.wk.get_schema()

    def _connect(self):
        if self.kinesis_client is None:
            logger.debug("Kinesis client is not present creating new session and client.")
            self.connection_object.session()
            self.connection_object.assume_role()
            self.kinesis_client = self.connection_object.input_stream_client()

    def to_stream_batch(self, profiles):
        """Send a list of profiles to kinesis.  Helpful in large publish operations."""
        if self.kinesis_client is None:
            self._connect()

        rejected_profiles = []
        valid_profiles = []
        status = []

        for profile in profiles:
            try:
                if isinstance(profile, str):
                    profile = json.loads(profile)

                cis_profile.profile.User(user_structure_json=profile).validate()
                valid_profiles.append(
                    dict(
                        Data=json.dumps(profile),
                        PartitionKey=self.config("publisher_id", namespace="cis", default="generic-publisher"),
                    )
                )
            except jsonschema.exceptions.ValidationError as e:
                logger.info("Reason for schema failure was: {}".format(e))
                status = 400
                sequence_number = None
                rejected_profiles.append({"status_code": status, "sequence_number": sequence_number})

        try:
            # Send to kinesis
            logger.debug("Attempting to send batch of profiles to kinesis.")
            results = self.kinesis_client.get("client").put_records(
                StreamName=self.kinesis_client.get("arn").split("/")[1], Records=valid_profiles
            )

            for result in results["Records"]:
                status.append(
                    {"status_code": result.get("ErrorCode", 200), "sequence_number": result.get("SequenceNumber")}
                )
        except ResourceNotFoundException:
            logger.debug("Profile publishing failed for batch. Could not find the kinesis stream in the account.")
            status = 404
            sequence_number = None
            status.append({"status_code": result.get("ErrorCode", 200), "sequence_number": result.get(sequence_number)})
        return status + rejected_profiles

    def to_stream(self, profile_json):
        """Send to kinesis and test the profile is valid."""
        if self.kinesis_client is None:
            self._connect()

        # Assume the following ( publisher has signed the new attributes and regenerated metadata )
        # Validate JSON schema
        try:
            cis_profile.profile.User(user_structure_json=profile_json).validate()
            logger.info(
                "Schema validated successfully for user_id: {}".format(profile_json.get("user_id").get("value"))
            )
        except jsonschema.exceptions.ValidationError as e:
            logger.info("Reason for schema failure was: {}".format(e))
            status = 400
            sequence_number = None
            return {"status_code": status, "sequence_number": sequence_number}

        # Optional would be to validate the signature at this time.
        # Pushing validation of crypto to integration for performance.

        try:
            # Send to kinesis
            logger.debug(
                "Attempting to send profile json to kinesis for user_id: {}".format(
                    profile_json.get("user_id").get("value")
                )
            )
            result = self.kinesis_client.get("client").put_record(
                StreamName=self.kinesis_client.get("arn").split("/")[1],
                Data=json.dumps(profile_json),
                PartitionKey=self.config("publisher_id", namespace="cis", default="generic-publisher"),
            )

            status = result["ResponseMetadata"]["HTTPStatusCode"]
            sequence_number = result.get("SequenceNumber", None)
        except ResourceNotFoundException:
            logger.debug(
                "Profile publishing failed for user: {}. Could not find the kinesis stream in the account.".format(
                    profile_json.get("user_id").get("value")
                )
            )
            status = 404
            sequence_number = None
        except InvalidArgumentException:
            logger.debug(
                "Profile publishing failed for user: {}. Arguments supplied were invalid.".format(
                    profile_json.get("user_id").get("value")
                )
            )
            status = 500
            sequence_number = None
        except Exception as e:
            logger.debug(
                "Profile publishing failed for user: {}. Due to unhandled exception: {}.".format(
                    profile_json.get("user_id").get("value"), e
                )
            )
            logger.error("An unhandled exception has occured: {}".format(e))
            status = 500
            sequence_number = None

        # Return status code and sequence number of message as dict
        return {"status_code": status, "sequence_number": sequence_number}


class Integrate(object):
    def __init__(self, user_id=None, primary_email="", access_token=""):
        self.access_token = access_token
        self.config = get_config()
        self.user_id = quote_plus(user_id)
        self.primary_email = quote_plus(primary_email)
        self.user_profile = None

    def should_publish(self, new_profile):
        self.user_profile = self._get_single_user()
        new_profile = cis_profile.profile.User(user_structure_json=new_profile)

        if self._is_new():
            return True
        else:
            old_profile = cis_profile.profile.User(user_structure_json=self.user_profile)
            logger.info("A user already exists in the vault for: {}".format(old_profile.user_id.value))
            complex_structures = ["access_information", "identities", "staff_information"]

            for attr in new_profile.as_dict():
                if attr != "schema":
                    old_attr = old_profile.as_dict()[attr]
                    new_attr = new_profile.as_dict()[attr]

                    logger.debug("Attempting comparison of two attributes for attr: {}".format(attr))

                    if attr not in complex_structures:
                        if old_attr["value"] == new_attr["value"]:
                            logger.debug("Attribute match.")
                            pass
                        else:
                            logger.debug(
                                "Attribute mismatch.  New: {}, Old: {}".format(new_attr["value"], old_attr["value"])
                            )
                            return True

                    if attr in complex_structures:
                        for nested_attr in new_attr:
                            if new_attr[nested_attr] == old_attr[nested_attr]:
                                pass
                            else:
                                return True
                    return False

    def merge(self, new_profile):
        self.user_profile = self._get_single_user()
        new_profile = cis_profile.profile.User(user_structure_json=new_profile)

        if self._is_new():
            logger.info("A new user will be created for: {}".format(new_profile.user_id.value))
            logger.info("Verifying all signatures for: {}".format(new_profile.user_id.value))
            publishers_verified = new_profile.verify_all_publishers(cis_profile.profile.User())
            assert publishers_verified is not None
            signatures_verified = new_profile.verify_all_signatures()
            logger.info("Signature result was: {} for: {}".format(signatures_verified, new_profile.user_id.value))
            return new_profile.as_dict()
        else:
            old_profile = cis_profile.profile.User(user_structure_json=self.user_profile)
            logger.info("A user already exists in the vault for: {}".format(old_profile.user_id.value))

        merged_profile_dict = cis_profile.profile.User().as_dict()
        complex_structures = ["access_information", "identities", "staff_information"]
        for attr in merged_profile_dict:
            if attr != "schema":
                old_attr = old_profile.as_dict()[attr]
                new_attr = new_profile.as_dict()[attr]

                logger.debug("Attempting comparison of two attributes for attr: {}".format(attr))

                if attr not in complex_structures:
                    can_publish = new_profile.verify_can_publish(
                        attr=new_attr, attr_name=attr, parent_name=None, previous_attribute=old_attr
                    )

                    if can_publish:
                        merged_profile_dict[attr] = new_attr

                elif attr in complex_structures:
                    for nested_attr in new_attr:
                        can_publish = new_profile.verify_can_publish(
                            attr=new_attr[nested_attr],
                            attr_name=nested_attr,
                            parent_name=attr,
                            previous_attribute=old_attr[nested_attr],
                        )

                        if can_publish:
                            merged_profile_dict[attr] = new_attr
        merged_profile_object = cis_profile.profile.User(user_structure_json=merged_profile_dict)
        logger.info("Verifying all signatures for: {}".format(new_profile.user_id.value))
        signatures_verified = merged_profile_object.verify_all_signatures()
        logger.info("Signature result was: {} for: {}".format(signatures_verified, new_profile.user_id.value))
        return merged_profile_dict

    def _get_base_uri(self):
        return self.config("person_api_uri", namespace="cis")

    def _get_person_route(self):
        return self.config("person_api_user_route", namespace="cis")

    def _get_query_string(self):
        if self.user_id != "":
            return self.user_id
        else:
            return self.primary_email

    def _get_single_user(self):
        if self.user_profile is None:
            print("getting some data")
            conn = http.client.HTTPSConnection(self._get_base_uri())
            headers = {"authorization": "Bearer {}".format(self.access_token)}
            conn.request("GET", "{}{}".format(self._get_person_route(), self._get_query_string()), headers=headers)
            res = conn.getresponse()

            if res.status == 200:
                data = json.loads(res.read())
            else:
                data = None
            return data
        else:
            return self.user_profile

    def _is_new(self):
        if self.user_profile is None:
            logger.info("This is a new user for: {}".format(self._get_query_string()))
            return True
        else:
            logger.info("The record already exists for: {}".format(self._get_query_string()))
            return False
