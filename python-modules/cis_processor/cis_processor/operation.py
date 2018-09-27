import boto3
import json

from cis_crypto import operation
from cis_identity_vault.models import user


class BaseProcessor(object):
    """Object to the basics to check the schema and integrate to dynamodb."""
    def __init__(self, event, dyanmodb_client, dynamodb_table):
        pass

    def event_type(self):
        """Returns dynamodb or kinesis based on payload structure.  For reuse in different stream triggers."""
        pass

    def needs_integration(self):
        """Retreive the profile from the dynamodb table.  Integrate it as needed."""
        pass

    def integration_authorized(self):
        """Truthy method returns if object should be put to dynamodb."""
        pass

    def _validate_schema(self):
        """Schema verified a final time prior to writing to the table."""
        pass

    def _to_dynamodb_schema(self):
        """Takes user profile and converts it to the datastructure necessary to put to dynamodb."""
        pass

    def _sequence_number_out_of_order(self):
        """Truthy method ensures sequence numbers are incrementing.  Reject if not by raising."""
        pass


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
