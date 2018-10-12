"""Send a profile: full or partial to kinesis.  Report back stream entry status."""
import cis_profile
import json
import jsonschema
import logging
import os

from boto.kinesis.exceptions import ResourceNotFoundException
from boto.kinesis.exceptions import InvalidArgumentException
from cis_aws import connect
from cis_publisher.common import get_config

logger = logging.getLogger(__name__)


class Publish(object):
    def __init__(self):
        self.config = get_config()
        self.connection_object = connect.AWS()
        self.kinesis_client = None
        self.schema = cis_profile.get_schema()

    def _connect(self):
        if self.kinesis_client is None:
            logger.debug('Kinesis client is not present creating new session and client.')
            self.connection_object.session()
            self.connection_object.assume_role()
            self.kinesis_client = self.connection_object.input_stream_client()

    def _validate_schema(self, profile_json):
        """Validate the structure that is passed in against the profilev2 schema."""
        logger.info(
            'Validating schema for profile json for user_id: {}'.format(
                profile_json.get('user_id').get('value')
            )
        )
        return jsonschema.validate(profile_json, self.schema)

    def to_stream(self, profile_json):
        """Send to kinesis and test the profile is valid."""
        if self.kinesis_client is None:
            self._connect()

        # Assume the following ( publisher has signed the new attributes and regenerated metadata )
        # Validate JSON schema
        try:
            self._validate_schema(profile_json)
            logger.debug(
                'The schema was successfully validated for user_id: {}'.format(
                    profile_json.get('user_id').get('value')
                )
            )
        except jsonschema.exceptions.ValidationError:
            logger.debug(
                'Schema validation failed for user_id: {}'.format(
                    profile_json.get('user_id').get('value')
                )
            )
            status = 400
            sequence_number = None
            return {'status_code': status, 'sequence_number': sequence_number}

        # Optional would be to validate the signature at this time.
        # Pushing validation of crypto to integration for performance.

        try:
            # Send to kinesis
            logger.debug('Attempting to send profile json to kinesis for user_id: {}'.format(
                    profile_json.get('user_id').get('value')
                )
            )
            result = self.kinesis_client.get('client').put_record(
                StreamName=self.kinesis_client.get('arn').split('/')[1],
                Data=json.dumps(profile_json),
                PartitionKey=self.config('publisher_id', namespace='cis', default='generic-publisher')
            )

            status = result['ResponseMetadata']['HTTPStatusCode']
            sequence_number = result.get('SequenceNumber', None)
        except ResourceNotFoundException:
            logger.debug(
                'Profile publishing failed for user: {}. Could not find the kinesis stream in the account.'.format(
                    profile_json.get('user_id').get('value')
                )
            )
            status = 404
            sequence_number = None
        except InvalidArgumentException:
            logger.debug(
                'Profile publishing failed for user: {}. Arguments supplied were invalid.'.format(
                    profile_json.get('user_id').get('value')
                )
            )
            status = 500
            sequence_number = None
        except Exception as e:
            logger.debug(
                'Profile publishing failed for user: {}. Due to unhandled exception: {}.'.format(
                    profile_json.get('user_id').get('value'), e
                )
            )
            logger.error('An unhandled exception has occured: {}'.format(e))
            status = 500
            sequence_number = None

        # Return status code and sequence number of message as dict
        return {'status_code': status, 'sequence_number': sequence_number}
