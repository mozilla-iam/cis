"""First class object for publishing messages to Mozilla Change Integration Service."""
import base64
import json
import logging

from cis.libs import connection
from cis.libs import encryption
from cis.libs import validation

from cis.settings import get_config


logger = logging.getLogger(__name__)


class ChangeNull(object):
    """Null Object to return if constructor failure."""
    def __init__(self):
        """
        :param publisher: Dictionary of information about publisher only required attr is id:
        :param signature: A pykmssig signature.  For now this is optional.
        :param profile_data: The complete user profile as json.
        """
        self.publisher = None
        self.signature = None
        self.profile_data = None

        # Centralize boto session for passing around.
        self.boto_session = None


class ChangeDelegate(object):
    def __init__(self, publisher, signature, profile_data):
        """
        :param publisher: Dictionary of information about publisher only required attr is id:
        :param signature: A pykmssig signature.  For now this is optional.
        :param profile_data: The complete user profile as json.
        """
        self.config = get_config()
        self.encryptor = None
        self.publisher = publisher
        self.profile_data = profile_data
        self.signature = signature
        self.user = None

        # Centralize boto session for passing around.
        self.boto_session = None
        self.lambda_client = None

    def _connect_aws(self):
        self.boto_session = connection.Connect(
            type='session',
            region='us-west-2'
        ).connect()

    def send(self):
        """
        :return: True or False based on exception.
        """

        if not self.boto_session:
            self._connect_aws()

        if self._validate_profile_data():
            result = self._invoke_validator(json.dumps(self._get_event_dict()).encode())
            logger.info('Invocation result is {result}'.format(result=result))
            return result

    def _get_event_dict(self):

        encrypted_profile = str(base64.b64encode(self._prepare_profile_data()))
        signature = self._generate_signature()

        return {
            'publisher': self.publisher,
            'profile': encrypted_profile,
            'signature': signature
        }

    def _nullify_empty_values(self, data):
        """
        Recursively update None values with empty string.
        DynamoDB workaround
        """
        new = {}
        for k in data.keys():
            v = data[k]
            if isinstance(v, dict):
                v = self._nullify_empty_values(v)
            if v is None:
                new[k] = 'NULL'
            else:
                new[k] = v
        return new

    def _prepare_profile_data(self):
        # Performing encryption and encoding on the user data and set on the object
        # Encode to base64 all payload fields
        if not self.encryptor:
            self.encryptor = encryption.Operation(boto_session=self.boto_session)

        logger.debug('Preparing profile data and encrypting profile.')

        # DynamoDB workaround
        data = self._nullify_empty_values(self.profile_data)
        encrypted_profile = self.encryptor.encrypt(json.dumps(data).encode('utf-8'))

        base64_payload = dict()
        for key in ['ciphertext', 'ciphertext_key', 'iv', 'tag']:
            base64_payload[key] = base64.b64encode(encrypted_profile[key]).decode('utf-8')

        encrypted_profile = json.dumps(base64_payload).encode('utf-8')
        logger.debug('Encryption process complete.')
        return encrypted_profile

    def _validate_profile_data(self):
        # Validate data prior to sending to CIS
        return validation.Operation(self.publisher, self.profile_data).is_valid()

    def _generate_signature(self):
        # If signature doesn't exist attempt to add one to the profile data.
        return {}

    def _invoke_validator(self, event):
        """
        Invoke lambda function in front of the CIS pipeline with data to be pushed to CIS

        :data: Data to be published to CIS (dict)
        """
        if not self.lambda_client:
            self.lambda_client = self.boto_session.client(service_name='lambda')

        logger.debug('Invoking the validator lambda function.')

        function_name = self.config('lambda_validator_arn', namespace='cis')
        response = self.lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=event
        )

        logger.debug('Status of the lambda invocation is {s}'.format(s=response))

        return response['StatusCode'] is 200


class Change(ChangeDelegate):
    """Guaranteed change object."""
    def __init__(self, publisher=None, signature=None, profile_data=None):
        try:
            ChangeDelegate.__init__(self, publisher, signature, profile_data)
        except Exception as e:
            logger.error('ChangeDelegate failed initialization returning nullObject.')
            ChangeNull.__init__(self)
