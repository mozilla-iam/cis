"""Iterative Stream Processor plugin for handling steps during data storage."""
import json
import os

from cis import user

from cis.libs import encryption
from cis.libs import streams
from cis.libs import validation


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
            print('dropping into validator')
            res = self._validator_stage()
        elif self.stage == 'streamtoidv':
            res = self._vault_stage()
        elif self.stage == 'idvtoauth0':
            # TBD fold in the authzero logic from idvtoauth0 in cis_functions
            pass
        else:
            # Unhandled pass for anything not handled in block.  Basically yield to block.
            pass
        return res

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

    def _validator_stage(self, kinesis_client=None):
        if self.user is None:
            self.user = user.Profile(profile_data=self.decrytped_profile)._retrieve_from_vault()

        result = validation.Operation(
            publisher=self.publisher,
            profile_data=self.decrytped_profile,
            user=self.user
        ).is_valid()

        if result == True and self.dry_run is not True:
            # Send to kinesis
            s = streams.Operation(
                boto_session=self.boto_session,
                publisher=self.publisher,
                signature=self.signature,
                encrypted_profile_data=self.encrypted_profile_data
            )

        return result

    def _vault_stage(self):
        u = user.Profile(self.decrytped_profile)

        if u._store_in_vault():
            return True
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
        self.user = None