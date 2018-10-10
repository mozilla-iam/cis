import boto3
import json

from base64 import b64decode
from cis_crypto import operation
from cis_processor import profile
from cis_profile import User as Profilev2User


from logging import getLogger

logger = getLogger(__name__)

class BaseProcessor(object):
    """Object to the basics to check the schema and integrate to dynamodb."""
    def __init__(self, event, dynamodb_client, dynamodb_table):
        self.event = event
        self.dynamodb_client = dynamodb_client
        self.dynamodb_table = dynamodb_table

    def _load_profiles(self):
        profile_delegate = profile.ProfileDelegate(self.event, self.dynamodb_client, self.dynamodb_table)
        self.profiles = profile_delegate.profiles

    def process(self):
        self._load_profiles()
        if self.needs_integration(self.profiles['new_profile'], self.profiles['old_profile']):
            # Check the rules
            self.profiles['new_user'].validate()
            self.profiles['new_user'].verify_all_publishers()
            pass
        else:
            pass

    def needs_integration(self, new_user_profile, old_user_profile):
        """Retreive the profile from the dynamodb table.  Integrate it as needed."""
        if old_user_profile is not None:
            old_user_profile_dict = old_user_profile.as_dict()
            new_user_profile_dict = new_user_profile.as_dict()
            for key in new_user_profile_dict:
                if new_user_profile_dict[key] != old_user_profile_dict[key]:
                    return True
        else:
            return True
        return False

    def integration_authorized(self):
        """Truthy method returns if object should be put to dynamodb."""
        pass

    def _to_dynamodb_schema(self):
        """Takes user profile and converts it to the datastructure necessary to put to dynamodb."""
        """
        dynamodb_schema = dict(
            primary_email=
            sequence_number=
            profile=
            user_id=
        )

        return dynamodb_schema
        """
        pass

    def _sequence_number_out_of_order(self):
        """Truthy method ensures sequence numbers are incrementing.  Reject if not by raising."""
        pass

    def event_type(self):
        """Return kinesis or dynamodb based on event structure."""
        if self.event.get('kinesis') is not None:
            return 'kinesis'

        if self.event.get('dynamodb') is not None:
            return 'dynamodb'


class VerifyProcessor(BaseProcessor):
    """Override operation object and introduce crypto sign/verify bits."""
    def __init__(self, event, dyanmodb_client, dynamodb_table):
        """Super the base object to reusability."""
        pass

    def verify_signature(self):
        """Takes an attribute and returns a dictionary using the strict verification mode in cis_crypto.
        Raises if the signature is not verifiable.
        """
        pass

    def is_correct_publisher_for_attr(self):
        """Takes the publisher kid and compares it with the schema.  Returns true or false for the attribute."""
        pass

    def _cache_well_known(self):
        """Grab the .well-known metadata every 15 minutes and serialize to cache."""
        pass

    def _fifteen_minutes_has_passed(self):
        """Let cache .well-known know to refresh the cache."""
        pass

    def _verify_signature(self, jws):
        """Truthy method takes a JWS and compares it to the .well-known file."""
        pass
