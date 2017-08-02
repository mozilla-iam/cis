"""First class object for publishing messages to Mozilla Change Integration Service."""
import base64
import json

from cis.libs import connection
from cis.libs import encryption
from cis.libs import validation

from cis.settings import get_config
from cis import user


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

        if self.boto_session is None:
            self._connect_aws()

        v = validation.Operation(
            publisher=self.publisher.get('id', None),
            profile_data=self.profile_data,
            user = self.user
        )

        if v.is_valid:
            encrypted_profile = str(base64.b64encode(self._prepare_profile_data()))
            signature = self._generate_signature()

            event = {
                'publisher': self.publisher,
                'profile': encrypted_profile,
                'signature': signature
            }

            result = self._invoke_validator(json.dumps(event).encode())

            return True
        else:
            return False

    def _prepare_profile_data(self):
        # Performing encryption and encoding on the user data and set on the object
        # Encode to base64 all payload fields
        if self.encryptor is None:
            self.encryptor = encryption.Operation(boto_session=self.boto_session)

        encrypted_profile = self.encryptor.encrypt(json.dumps(self.profile_data).encode('utf-8'))

        base64_payload = dict()
        for key in ['ciphertext', 'ciphertext_key', 'iv', 'tag']:
            base64_payload[key] = base64.b64encode(encrypted_profile[key]).decode('utf-8')

        encrypted_profile = json.dumps(base64_payload).encode('utf-8')
        return encrypted_profile

    def _validate_profile_data(self):
        # Validate data prior to sending to CIS
        v = validation.Operation(self.publisher, self.profile_data)
        return v.is_valid()

    def _generate_signature(self):
        # If signature doesn't exist attempt to add one to the profile data.
        return {}

    def _invoke_validator(self, event):
        """
        Invoke lambda function in front of the CIS pipeline with data to be pushed to CIS

        :data: Data to be published to CIS (dict)
        """
        if self.lambda_client is None:
            self.lambda_client = self.boto_session.client(service_name='lambda')

        function_name = self.config('lambda_validator_arn', namespace='cis')
        response = self.lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=event
        )

        return response

class Change(ChangeDelegate):
    """Guaranteed change object."""
    def __init__(self, publisher=None, signature=None, profile_data=None):
        try:
            ChangeDelegate.__init__(self, publisher, signature, profile_data)
        except Exception as e:
            print(e)
            print("returning null object")
            ChangeNull.__init__(self)
