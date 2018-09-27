import json
import logging
import os
import requests
import yaml
from jose import jwk
from jose import jws
from jose.exceptions import JWSError
from cis_crypto import get_config
from cis_crypto import secret

logger = logging.getLogger(__name__)
# Note:
# These attrs on sign/verify could be refactored to use object inheritance.  Leaving as is for now for readability.


class Sign(object):
    def __init__(self):
        self.config = get_config()
        self.key_name = self.config('signing_key_name', namespace='cis', default='file')
        self._jwk = None
        self.secret_manager = self.config('secret_manager', namespace='cis', default='file')
        self.payload = None

    def load(self, data):
        """Loads a payload to the object and ensures that the thing is serializable."""
        try:
            data = yaml.safe_load(data)
        except yaml.scanner.ScannerError:
            logger.info('This file is likely not YAML.  Attempting JSON load.')
        except AttributeError:
            logger.info('This file is likely not YAML.  Attempting JSON load.')

        if isinstance(data, str):
            data = json.loads(data)
        else:
            pass

        self.payload = data
        return self.payload

    def jws(self):
        """Assumes you loaded a payload.  Returns a jws."""
        jwk = self._get_key()
        sig = jws.sign(self.payload, jwk.to_dict(), algorithm='RS256')
        return sig

    def _get_key(self):
        if self._jwk is None:
            manager = secret.Manager(provider_type=self.secret_manager)
            self._jwk = manager.get_key(key_name=self.key_name)
        return self._jwk


class Verify(object):
    def __init__(self):
        self.config = get_config()
        # Provide file or URL as opts.
        self.well_known_mode = self.config('well_known_mode', namespace='cis', default='file')
        self.public_key_name = None  # Optional for use with file based well known mode
        self.jws_signature = None

    def load(self, jws_signature, payload=None):
        """Takes data in the form of a dict() and a JWS sig."""
        # Store the original form in the jws_signature attribute
        self.jws_signature = jws_signature

    def _get_public_key(self):
        """Returns a jwk construct for the public key and mode specified."""
        if self.well_known_mode == 'file':
            key_dir = self.config(
                'secret_manager_file_path',
                namespace='cis',
                default=(
                    '{}/.mozilla-iam/keys/'.format(
                        os.path.expanduser('~')
                    )
                )
            )
            key_name = self.config('public_key_name', namespace='cis', default='access-file-key')
            file_name = '{}'.format(key_name)
            fh = open((os.path.join(key_dir, file_name)), 'rb')
            key_content = fh.read()
            key_construct = jwk.construct(key_content, 'RS256')
            return [key_construct.to_dict()]
        elif self.well_known_mode == 'http' or self.well_known_mode == 'https':
            # Go get it from the .well-known endpoint and load as json
            # return a dictionary of the json loaded data
            well_known_url = self.config('well_known_url', namespace='cis')
            # XXX TBD Cache this content and retreive at 15-minute intervals.
            res = requests.get(well_known_url)

            if res.status_code == 200:
                key_list = self._reduce_keys(res.json())
                return key_list

    def _reduce_keys(self, well_known_response):
        access_file_keys = well_known_response['access_file']['jwks_keys']
        publishers_supported = well_known_response['publishers_supported']

        keys = []

        if 'access-file-key' in self.config('public_key_name', namespace='cis', default='access-file-key'):
            return access_file_keys
        else:
            # If not an access key verification this will attempt to verify against any listed publisher.
            keys = publishers_supported[publisher]['jwks_keys']
            for key in range(len(keys)):
                keys.append(
                    key
                )
        return keys

    def jws(self):
        """Assumes you loaded a payload.  Return the same jws or raise a custom exception."""
        key_material = self._get_public_key()

        if isinstance(key_material, list):
            logger.debug('Multiple keys returned.  Attempting match.')
            for key in key_material:
                key.pop('x5t', None)
                key.pop('x5c', None)
                logger.info('Attempting to match against: {}'.format(key))
                try:
                    sig = jws.verify(self.jws_signature, key, algorithms='RS256', verify=True)
                    logger.info('Matched a verified signature for: {}'.format(key))
                    return sig
                except JWSError as e:
                    logger.error(e)
        raise JWSError('The signature could not be verified for any trusted key.')


class StrictVerify(Verify):
    """Strict verify exists for use in the stream processors.  If a profile update needs to be ensured to have come
    from a specific publisher.  Returns the matching key instead of a jws."""
    def __init__(self):
        super().__init__()

    def _get_public_key(self):
        """Returns a jwk construct for the public key and mode specified."""
        if self.well_known_mode == 'file':
            key_dir = self.config(
                'secret_manager_file_path',
                namespace='cis',
                default=(
                    '{}/.mozilla-iam/keys/'.format(
                        os.path.expanduser('~')
                    )
                )
            )
            key_name = self.config('public_key_name', namespace='cis', default='access-file-key')
            file_name = '{}'.format(key_name)
            fh = open((os.path.join(key_dir, file_name)), 'rb')
            key_content = fh.read()
            key_construct = jwk.construct(key_content, 'RS256')
            return key_construct.to_dict()
        elif self.well_known_mode == 'http' or self.well_known_mode == 'https':
            # Go get it from the .well-known endpoint and load as json
            # return a dictionary of the json loaded data
            well_known_url = self.config('well_known_url', namespace='cis')
            # XXX TBD Cache this content and retreive at 15-minute intervals.
            res = requests.get(well_known_url)

            if res.status_code == 200:
                supported_publishers = res.json().get('publishers_supported')
                return supported_publishers

    def jws(self, publisher_authority=None):
        """Assumes you loaded a payload.  Return the same jws or raise a custom exception."""
        publisher_keys = self._get_public_key()
        publisher_authority_public_keys = publisher_keys.get(publisher_authority)
        if publisher_authority_public_keys is not None:
            for possible_key in publisher_authority_public_keys.get('jwks_keys'):
                sig = jws.verify(self.jws_signature, possible_key, algorithms='RS256', verify=True)
                return sig
        raise JWSError('The signature could not be verified for any trusted key.')
