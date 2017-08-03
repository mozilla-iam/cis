"""Iterative Stream Processor plugin for handling steps during data storage."""
import base64
import json
import logging
import os

from cis import user

from cis.libs import encryption
from cis.libs import streams
from cis.libs import validation


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

        if self.stage == 'validator':
            logger.info('Validator logic activated.')
            res = self._validator_stage()

            if res is True:
                logger.info('Payload valid sending to kinesis.')
                stream_operation = streams.Operation(
                    boto_session=self.boto_session,
                    publisher=self.publisher,
                    signature=self.signature,
                    encrypted_profile_data=self.encrypted_profile_data
                )

                if self.kinesis_client is not None:
                    stream_operation.kinesis_client = self.kinesis_client

                kinesis_result = stream_operation.to_kinesis()

                if kinesis_result['ResponseMetadata']['HTTPStatusCode'] == 200:
                    res = True
        elif self.stage == 'streamtoidv':
            res = self._vault_stage()
        elif self.stage == 'idvtoauth0':
            # TBD fold in the authzero logic from idvtoauth0 in cis_functions
            pass
        else:
            # Unhandled pass for anything not handled in block.  Basically yield to block.
            res = None

        logger.info('The result of the change was {r}'.format(r=res))
        return res

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

    def _get_stage(self):
        # Let the object know what phase of operation we are running in.
        stage = os.environ.get('APEX_FUNCTION_NAME', None)
        return stage

    def _validator_stage(self, kinesis_client=None):
        if self.user is None:
            self.user = user.Profile(
                boto_session=self.boto_session,
                profile_data=self.decrytped_profile
            ).retrieve_from_vault()

        result = validation.Operation(
            publisher=self.publisher,
            profile_data=self.decrytped_profile,
            user=self.user
        ).is_valid()

        if result is True and self.dry_run is not True:
            # Send to kinesis
            s = streams.Operation(
                boto_session=self.boto_session,
                publisher=self.publisher,
                signature=self.signature,
                encrypted_profile_data=self.encrypted_profile_data
            )

            logger.info('Result sent to kinesis status is {s}'.format(s=s))

        return result

    def _vault_stage(self):
        if self.user is None:
            u = user.Profile(
                boto_session=self.boto_session,
                profile_data=self.decrytped_profile
            )
            return u.store_in_vault()
        else:
            return False

    def _auth_zero_stage(self):
        # TBD in next sprint.
        pass


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
            OperationDelegate.__init__(self, boto_session, publisher, signature, encrypted_profile_data)

        except Exception as e:
            OperationNull().__init__(self)
            logger.info('NullObject returned due to {e}'.format(e=e))
        self.user = None
