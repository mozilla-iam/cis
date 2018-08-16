import json
import os
from jose import jwk
from jose import jws
from cis_crypto import get_config
from cis_crypto import secret


# Note:
# These attrs on sign/verify could be refactored to use object inheritance.  Leaving as is for now for readability.

class Sign(object):
    def __init__(self):
        self.config = get_config()
        self.key_name = self.config('signing_key_name', namespace='cis', default='file')
        self.secret_manager = self.config('secret_manager', namespace='cis', default='file')
        self.payload = None

    def load(self, data):
        """Loads a payload to the object and ensures that the thing is serializable."""
        ### XXX TBD solve the deterministic json deserializing problem.  This is probably NP-Hard.
        # Do the right thing if we are passed an str instead of a dict.
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
        manager = secret.Manager(provider_type=self.secret_manager)
        return manager.get_key(key_name=self.key_name)


class Verify(object):
    def __init__(self):
        self.config = get_config()
        # Provide file or URL as opts.
        self.well_known_mode = self.config('well_known_mode', namespace='cis', default='file')
        self.public_key_name = None # Optional for use with file based well known mode
        self.jws_signature = None
        self.payload = None

    def load(self, jws_signature, payload=None):
        """Takes data in the form of a dict() and a JWS sig."""

        # Note data is an optional arg.  If passed into this method it will compare the dict with the data in the sig.

        # Store the original form in the jws_signature attribute
        self.jws_signature = jws_signature

        if payload is not None:
            # There is data.  Compare the two dicts and ensure they match.
            pass
        pass

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
            key_name = self.config('public_key_name', namespace='cis')
            file_name = '{}.pub.pem'.format(key_name)
            fh = open((os.path.join(key_dir, file_name)), 'rb')
            key_content = fh.read()
            key_construct = jwk.construct(key_content, 'RS256')
            return key_construct.to_dict()
        elif self.well_known_mode is 'http':
            # Go get it from the .well-known endpoint and load as json
            # return a dictionary of the json loaded data
            pass

    def jws(self):
        """Assumes you loaded a payload.  Return the same jws or raise a custom exception."""
        jwk = self._get_public_key()
        sig = jws.verify(self.jws_signature, jwk, algorithms='RS256', verify=True)
        # XXX TBD failed verification will raise JWSError log in mozilla-iam format the custom exception
        return sig
