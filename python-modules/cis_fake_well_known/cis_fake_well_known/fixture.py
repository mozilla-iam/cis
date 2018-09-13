import os
from jose import jwk
from cis_fake_well_known import get_config
from cis_fake_well_known import load_key_file


class Key(object):
    """Return a private key fixture for use in sign verify operations."""
    def __init__(self, key_name=None, key_type=None, encoded=True):
        """Takes a key type of either publisher or access file."""
        self.key_type = key_type
        self.key_name = key_name
        self.encoded = encoded

    @property
    def material(self):
        """Return private key material for the initialized key type."""
        key_content = load_key_file(self.key_name, self.key_type, True)

        if self.encoded is False:
            # If encoded set to false return the raw pem as bytes
            return key_content
        else:
            # Else return the key material in JWKS form as required in n
            jwk_contruct = jwk.construct(key_content, algorithm='RS256')
            key_content = jwk_contruct.to_dict()

        return key_content

    def available_keys(self):
        """Lists the keys the module has access to."""
        config = get_config()
        key_dir = config('jwks_key_path', namespace='cis', default=('{}/keys'.format(os.path.dirname(__file__))))
        return os.listdir(key_dir)
