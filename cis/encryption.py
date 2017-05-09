import boto3
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from cis import settings


kms = boto3.client('kms')


def encrypt(plaintext, encryption_context=None):
    """
    Encrypt CIS payload using keys derived from KMS.

    :plaintext: Payload to be encrypted
    """

    data_key = kms.generate_data_key(
        KeyId=settings.ARN_MASTER_KEY,
        KeySpec='AES_256',
        EncryptionContext=encryption_context
    )
    plaintext_key = data_key.get('Plaintext')
    ciphertext_key = data_key.get('CiphertextBlob')
    iv = os.urandom(12)

    encryptor = Cipher(
        algorithms.AES(plaintext_key),
        modes.GCM(iv),
        backend=default_backend()
    ).encryptor()

    ciphertext = encryptor.update(plaintext) + encryptor.finalize()

    return {
        'ciphertext': ciphertext,
        'ciphertext_key': ciphertext_key,
        'iv': iv,
        'tag': encryptor.tag
    }


def decrypt(ciphertext, ciphertext_key, iv, tag, encryption_context=None):
    """
    Decrypt CIS payload using KMS encrypted key.

    :ciphertext: encrypted payload
    :ciphertext_key: encrypted KMS derived key
    :iv: AES initialization vector used to encrypt payload
    :tag: AES GCM authentication code
    """

    plaintext_key = kms.decrypt(
        CiphertextBlob=ciphertext_key, EncryptionContext=encryption_context).get('Plaintext')

    decryptor = Cipher(
        algorithms.AES(plaintext_key),
        modes.GCM(iv, tag),
        backend=default_backend()
    ).decryptor()

    return decryptor.update(ciphertext) + decryptor.finalize()
