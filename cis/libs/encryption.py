import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from cis.settings import get_config

class Operation(object):
    def __init__(self, boto_session):
        self.config = get_config()
        self.data_key = None
        self.iv = None

        try:
            self.kms = boto_session.client(service_name='kms')
        except Exception as e:
            self.kms = None

        self.kms_key_arn = self.config('arn_master_key', namespace='cis')
        self.plaintext_key = None

    def encrypt(self, plaintext, encryption_context={}):
        """
        Encrypt CIS payload using keys derived from KMS.
    
        :plaintext: Payload to be encrypted
        """
        if self.data_key is None:
            self.data_key = self._get_data_key_from_kms()

        if self.iv is None:
            self.iv = self._get_initialization_vector()

        plaintext_key = self.data_key.get('Plaintext')
        ciphertext_key = self.data_key.get('CiphertextBlob')

        encryptor = Cipher(
            algorithms.AES(plaintext_key),
            modes.GCM(self.iv),
            backend=default_backend()
        ).encryptor()

        ciphertext = encryptor.update(plaintext) + encryptor.finalize()

        return {
            'ciphertext': ciphertext,
            'ciphertext_key': ciphertext_key,
            'iv': self.iv,
            'tag': encryptor.tag
        }

    def decrypt(self, ciphertext, ciphertext_key, iv, tag, encryption_context={}):
        """
        Decrypt CIS payload using KMS encrypted key.
    
        :ciphertext: encrypted payload
        :ciphertext_key: encrypted KMS derived key
        :iv: AES initialization vector used to encrypt payload
        :tag: AES GCM authentication code
        """
        if self.plaintext_key is None:
            self.plaintext_key = self._decrypt_envelope_with_kms(ciphertext_key, encryption_context)

        decryptor = Cipher(
            algorithms.AES(self.plaintext_key),
            modes.GCM(iv, tag),
            backend=default_backend()
        ).decryptor()

        return decryptor.update(ciphertext) + decryptor.finalize()

    def _get_initialization_vector(self):
        return os.urandom(12)

    def _get_data_key_from_kms(self):
        """
        
        :return: Amazon KMS Data key for use with envelope encryption.
        """
        data_key = kms.generate_data_key(
            KeyId=self.kms_key_arn,
            KeySpec='AES_256',
            EncryptionContext=encryption_context
        )
        return data_key

    def _decrypt_envelope_with_kms(self, ciphertext_key, encryption_context = {}):
        """
        
        :param ciphertext_key: The cipher text key to use to perform the decryption
        :param encryption_context: Usually an empty dict.  Future proofing for auth encryption.
        :return: A plaintext form of the AES key.
        """
        plaintext_key = self.kms.decrypt(
            CiphertextBlob=ciphertext_key, EncryptionContext=encryption_context
        ).get('Plaintext')

        return plaintext_key