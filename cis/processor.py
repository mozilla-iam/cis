"""Iterative Stream Processor plugin for handling steps during data storage."""
import base64
import json
import logging
import os

from cis import user

from cis.libs import encryption
from cis.libs import streams
from cis.libs import utils
from cis.libs import validation

from pykmssig import crypto


utils.StructuredLogger(name=__name__, level=logging.INFO)
logger = logging.getLogger(__name__)


class OperationDelegate(object):
    def __init__(self, boto_session=None, publisher=None, signature=None, encrypted_profile_data=None):
        self.boto_session = boto_session
        self.dry_run = True
        self.decryptor = encryption.Operation(boto_session=boto_session)
        self.encrypted_profile_data = encrypted_profile_data
        self.kinesis_client = None
        self.publisher = publisher
        self.signature = signature
        self.stage = self._get_stage()
        self.user = None

    def run(self):
        # Determine what stage of processing we are in and call the corresponding functions.
        self.decrytped_profile = json.loads(self._decrypt_profile_packet())

        if self.signature == {} or self.signature is None:
            self.signature = self.decrytped_profile.get('signature')

        self._verify_signature()

    def _decode_profile_packet(self):
        for key in ['ciphertext', 'ciphertext_key', 'iv', 'tag']:
            self.encrypted_profile_data[key] = base64.b64decode(self.encrypted_profile_data[key])

    def _decrypt_profile_packet(self):
        self._decode_profile_packet()
        return self.decryptor.decrypt(
            ciphertext=self.encrypted_profile_data.get('ciphertext'),
            ciphertext_key=self.encrypted_profile_data.get('ciphertext_key'),
            iv=self.encrypted_profile_data.get('iv'),
            tag=self.encrypted_profile_data.get('tag')
        )

    def _verify_signature(self):
        sig_result = self._decrypt_and_verify()

        if sig_result.get('status') == 'valid':
            return True
        else:
            return False

    def _decrypt_and_verify(self):
        o = crypto.Operation()
        result = o.verify(
            ciphertext=base64.b64decode(self.signature),
            plaintext=json.dumps(self.decrytped_profile)
        )

        logger.info('The result of pykmssig operation was: {}'.format(result))

        return result

    def _get_stage(self):
        # Let the object know what phase of operation we are running in.
        stage = os.environ.get('APEX_FUNCTION_NAME', None)
        return stage

    def _auth_zero_stage(self):
        # TBD in next sprint.
        pass


class ValidatorOperation(OperationDelegate):
    def __init__(self, boto_session, publisher, signature, encrypted_profile_data):
        OperationDelegate.__init__(self, boto_session, publisher, signature, encrypted_profile_data)

    def run(self):
        logger.info('Attempting to load stage processor logic: {}'.format(self.stage))
        self.decrytped_profile = json.loads(self._decrypt_profile_packet())

        if self.signature == {} or self.signature is None:
            logger.info('Signature not set on object. Retreiving from profile packet.')
            self.signature = self.decrytped_profile.get('signature')

        return(self._publish_to_stream(self._validator_stage()))

    def _validator_stage(self, kinesis_client=None):
        if self.user is None:
            self.user = user.Profile(
                boto_session=self.boto_session,
                profile_data=self.decrytped_profile
            ).retrieve_from_vault()

        if self._verify_signature():
            logger.info(
                'Signature verified successfully. Running additional validation plugins for user_id: {}'.format(
                    self.decrytped_profile.get('user_id')
                )
            )

            result = validation.Operation(
                publisher=self.publisher,
                profile_data=self.decrytped_profile,
                user=self.user
            ).is_valid()
        else:
            result = False

        logger.info(
            'Result of the validation operation for user_id: {} is {}'.format(
                self.decrytped_profile.get('user_id'),
                result
            )
        )

        return result

    def _publish_to_stream(self, validation_status=False):
        if validation_status is True:
            stream_operation = streams.Operation(
                boto_session=self.boto_session,
                publisher=self.publisher,
                signature=self.signature,
                encrypted_profile_data=self.encrypted_profile_data
            )

            if self.kinesis_client is not None:
                stream_operation.kinesis_client = self.kinesis_client

            kinesis_result = stream_operation.to_kinesis()
            logger.info(
                'The profile for user_id: {} was sent to kinesis with sequenceNumber: {}'.format(
                    self.decrytped_profile.get('user_id'),
                    kinesis_result.get('SequenceNumber')
                )
            )
            return(kinesis_result['ResponseMetadata']['HTTPStatusCode'] is 200)
        else:
            return False


class StreamtoVaultOperation(OperationDelegate):
    def __init__(self, boto_session, publisher, signature, encrypted_profile_data):
        logger.info('Stream to IDVault operation initialized for publisher: {}'.format(publisher))
        OperationDelegate.__init__(self, boto_session, publisher, signature, encrypted_profile_data)

    def run(self):
        logger.info('Attempting to load stage processor logic: {}'.format(self.stage))
        self.decrytped_profile = json.loads(self._decrypt_profile_packet())
        logger.info('Processing from publisher {pub} for profile: {p}'.format(
            pub=self.publisher, p=self.decrytped_profile.get('user_id')))
        return(self._vault_stage())

    def _vault_stage(self):
        if not self.user:
            self.user = user.Profile(
                boto_session=self.boto_session,
                profile_data=self.decrytped_profile
            )

        return self.user.store_in_vault()


class OperationNull(object):
    def __init__(self, boto_session=None, publisher=None, signature=None, encrypted_profile_data=None):
        self.boto_session = boto_session
        self.decryptor = None
        self.encrypted_profile_data = None
        self.publisher = None
        self.signature = None
        self.stage = None
        self.user = None


class Operation(OperationDelegate):
    def __init__(self, boto_session=None, publisher=None, signature=None, encrypted_profile_data=None):
        try:
            logger.info('Processor operation initialized for profile packet from publisher: {}.'.format(publisher))
            OperationDelegate.__init__(self, boto_session, publisher, signature, encrypted_profile_data)

        except Exception as e:
            OperationNull().__init__(self)
            logger.info('NullObject returned due to {e}'.format(e=e))
        self.user = None
