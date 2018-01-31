"""First class object for publishing messages to Mozilla Change Integration Service."""
import base64
import json
import logging

from cis.libs import api
from cis.libs import connection
from cis.libs import encryption
from cis.libs import utils
from cis.libs import validation

from cis.settings import get_config

from pykmssig import crypto

utils.StructuredLogger(name=__name__, level=logging.INFO)
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
        logger.debug('Connected to AWS using a boto_session.')

    def send(self):
        """
        :return: True or False based on exception.
        """

        if not self.boto_session:
            logger.debug('No boto_session present in object. Connecting to AWS.')
            self._connect_aws()

        if self._validate_profile_data():
            result = self._invoke_validator(json.dumps(self._get_event_dict()).encode())
            logger.info('Validator invocation complete with result: {} for user_id: {}'.format(
                result, self.profile_data.get('user_id'))
            )
            return result

    def _get_event_dict(self):
        profile_data = self._prepare_profile_data()

        # Ensure for json serialization that b64 is always string type.

        encrypted_profile = base64.b64encode(
            profile_data.encode('utf-8')  # Take our profile data to bytes type always to satisfy python 3
        ).decode()

        if self.signature is None or self.signature == {}:
            self.signature = self._generate_signature(json.dumps(self.profile_data))

        return {
            'publisher': self.publisher,
            'profile': encrypted_profile,
            'signature': self.signature
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
            # explicitly check for None value and empty string.
            if v is None or v == '':
                new[k] = 'NULL'
            else:
                new[k] = v
        return new

    def _prepare_profile_data(self):
        # Performing encryption and encoding on the user data and set on the object
        # Encode to base64 all payload fields
        if not self.encryptor:
            logger.info(
                'Encryptor not present on object.  Intializing encryptor for change for user: {}'.format(
                    self.profile_data.get('user_id')
                )
            )
            self.encryptor = encryption.Operation(boto_session=self.boto_session)

        logger.info(
            'Preparing profile data and encrypting profile for user_id: {}.'.format(
                self.profile_data.get('user_id')
            )
        )

        # Reintegrate groups this publisher is not authoritative for.
        self._reintegrate_profile_with_api()

        # DynamoDB workaround
        self.profile_data = self._nullify_empty_values(self.profile_data)

        # Actually encrypt the profile
        encrypted_profile = self.encryptor.encrypt(json.dumps(self.profile_data).encode('utf-8'))

        base64_payload = dict()
        # Build up our encryption envelope
        for key in ['ciphertext', 'ciphertext_key', 'iv', 'tag']:
            base64_payload[key] = base64.b64encode(encrypted_profile[key]).decode('utf-8')

        # Dump that out to a string
        encrypted_profile = json.dumps(base64_payload)
        logger.info('Encryption process complete for change for user_id: {}.'.format(self.profile_data.get('user_id')))
        return encrypted_profile

    def _validate_profile_data(self):
        # Validate data prior to sending to CIS
        logger.info(
            'Validating the change prior to sending the profile for user: {}.'.format(
                self.profile_data.get('user_id')
            )
        )
        result = validation.Operation(self.publisher, self.profile_data).is_valid()
        logger.info('Change validation result is: {} for user_id: {}'.format(result, self.profile_data.get('user_id')))
        return result

    def _retrieve_from_vault(self):
        person = api.Person(
            person_api_config={
                'audience': self.config('person_api_audience', namespace='cis'),
                'client_id': self.config('oauth2_client_id', namespace='cis'),
                'client_secret': self.config('oauth2_client_secret', namespace='cis'),
                'oauth2_domain': self.config('oauth2_domain', namespace='cis'),
                'person_api_url': self.config('person_api_url', namespace='cis'),
                'person_api_version': self.config('person_api_version', namespace='cis')
            }
        )

        # Retrieve the profile from the CIS API
        vault_profile = person.get_userinfo(self.profile_data.get('user_id'))

        logger.info('Vault profile retrieved for user: {}.'.format(self.profile_data.get('user_id')))
        return vault_profile

    def _reintegrate_profile_with_api(self):
        vault_profile = self._retrieve_from_vault()

        if vault_profile is not None:
            logger.debug('Vault profile retreived for existing vault user: {}'.format(vault_profile.get('user_id')))
            publisher_groups = self.profile_data.get('groups', [])
            vault_groups = vault_profile.get('groups', [])

            reintegrated_groups = []

            for group in publisher_groups:
                # Publishers are only allowed to publish groups prefixed with their id.
                if group.split('_')[0] == self.publisher.get('id'):
                    reintegrated_groups.append(group)

            for group in vault_groups:
                # Trust the data in the vault for all other group prefixes.
                if group.split('_')[0] != self.publisher.get('id'):
                    reintegrated_groups.append(group)

            logger.info(
                'Groups successfully reintegrated for user_id {} for change request from publisher {}.'.format(
                    self.profile_data.get('user_id'),
                    self.publisher.get('id')
                )
            )

            self.stats(vault_profile, self.profile_data)
            # Replace the data in the profile with our reintegrated group list.
            self.profile_data['groups'] = reintegrated_groups

    def stats(self, current_user_profile, proposed_change):
        if current_user_profile is not None:
            user_id = proposed_change.get('user_id')

            current_group_count = len(current_user_profile.get('groups', []))
            new_group_count = len(proposed_change.get('groups', []))

            net_change = new_group_count - current_group_count

            logger.info(
                'The proposed change will result in user_id: {} having {} number of groups.'.format(
                    user_id, new_group_count
                )
            )

            logger.info(
                'The net group change for user_id: {} is {} number of groups.'.format(user_id, net_change)
            )

    def _generate_signature(self, profile_data):
        # If signature doesn't exist attempt to add one to the profile data.
        o = crypto.Operation()
        sig = base64.b64encode(o.sign(plaintext=profile_data))
        logger.info('Signature generated for user_id: {}. The signature is {}'.format(
            self.profile_data.get('user_id'), sig)
        )
        return sig.decode()

    def _invoke_validator(self, event):
        """
        Invoke lambda function in front of the CIS pipeline with data to be pushed to CIS

        :data: Data to be published to CIS (dict)
        """
        if not self.lambda_client:
            self.lambda_client = self.boto_session.client(service_name='lambda')

        logger.info(
            'Invoking the validator lambda function for a change for {}. Signature at time of entry is: {}'.format(
                self.profile_data.get('user_id'),
                self.signature
            )
        )

        function_name = self.config('lambda_validator_arn', namespace='cis')
        response = self.lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=event
        )

        logger.info(
            'Status of the lambda invocation is {} for user_id: {}'.format(
                response,
                self.profile_data.get('user_id')
            )
        )

        return response['StatusCode'] is 200


class Change(ChangeDelegate):
    """Guaranteed change object."""
    def __init__(self, publisher=None, signature=None, profile_data=None):
        try:
            ChangeDelegate.__init__(self, publisher, signature, profile_data)
        except Exception as e:
            logger.error('ChangeDelegate failed initialization returning nullObject: {}.'.format(e))
            ChangeNull.__init__(self)
