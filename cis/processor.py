"""Iterative Stream Processor plugin for handling steps during data storage."""
import json
import os

from cis.libs import encryption
from cis.libs import streams
from cis.libs import validation


class OperationDelegate(object):
    def __init__(self, boto_session=None, publisher=None, signature=None, encrypted_profile_data=None):
        self.boto_session = boto_session
        self.decryptor = encryption.Operation(boto_session=boto_session)
        self.encrypted_profile_data = encrypted_profile_data
        self.publisher = publisher
        self.signature = signature
        self.stage = self._get_stage()

    def run(self):
        # Determine what stage of processing we are in and call the corresponding functions.

        self.decrytped_profile = json.loads(self._decrypt_profile_packet())


        if self.stage is 'validator':
            pass
        elif self.stage is 'streamtoidv':
            pass
        elif self.stage is 'idvtoauth0':
            pass
        else:
            # Unhandled pass
            pass

    def _decrypt_profile_packet(self):
        return self.decryptor.decrypt(
            ciphertext=self.encrypted_profile_data.get('ciphertext'),
            ciphertext_key=self.encrypted_profile_data.get('ciphertext_key'),
            iv=self.encrypted_profile_data.get('iv'),
            tag=self.encrypted_profile_data.get('tag')

        )

    def _get_stage(self):
        # Let the object know what phase of operation we are running in.
        stage = os.environ.get('AWS_LAMBDA_FUNCTION_NAME').split('_')[3]
        return stage

    def _validator_stage(self):
        validation.Operation()
        pass

    def _vault_stage(self):
        pass

    def _auth_zero_stage(self):
        pass


class OperationNull(object):
    def __init__(self, boto_session=None, publisher=None, signature=None, encrypted_profile_data=None):
        self.boto_session = boto_session
        self.decryptor = None
        self.encrypted_profile_data = None
        self.publisher = None
        self.signature = None
        self.stage = None


class Operation(OperationDelegate):
    def __init__(self, boto_session=None, publisher=None, signature=None, encrypted_profile_data=None):
        try:
            OperationDelegate.__init__(self, boto_session, publisher, signature, encrypted_profile_data)

        except Exception as e:
            OperationNull().__init__(self)
