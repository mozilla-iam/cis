import os
from faker import Faker
from jose import jwk
from uuid import uuid4
from cis_fake_well_known.common import get_config
from cis_fake_well_known.common import load_key_file


class MozillaIAM(object):
    def __init__(self):
        self._config = get_config()
        self.well_known_publisher_names = ['cis', 'mozilliansorg', 'ldap', 'hris', 'access_provider']
        self.randomize_publishers = bool(
            self._config('randomize_publisher_names', namespace='cis', default='True')
        )

        self.publisher_keys = self._load_publisher_keys()

    def data(self):
        well_known_data_structure = {
            'oidc_discovery_uri': self._get_oidc_discovery_uri(),
            'access_file': self._get_access_file(),
            'person_api': self._get_person_api(),
            'publishers_supported': self._get_publishers()
        }

        return well_known_data_structure

    def _load_publisher_keys(self):
        keys = os.listdir(os.path.dirname(__file__) + '/keys')
        publisher_keys = []
        for key_name in keys:
            if 'publisher' in key_name and 'pub' in key_name:
                if self.randomize_publishers is True:
                    fake_publisher_name = Faker().domain_name().replace('.', '_')
                    key_content = load_key_file(key_name.split('.')[0], 'pub')
                else:
                    fake_publisher_name = self.well_known_publisher_names.pop()
                    key_content = load_key_file(key_name.split('.')[0], 'pub')
                jwk_construct = jwk.construct(key_content, algorithm='RS256')

                jwk_dict = jwk_construct.to_dict()

                for k, v in jwk_dict.items():
                    if isinstance(v, bytes):
                        jwk_dict[k] = v.decode()

                jwk_dict['use'] = 'sig'
                jwk_dict['kid'] = uuid4().hex
                jwk_dict['x5c'] = 'unsupported'

                if self.randomize_publishers is True:
                    publisher_keys.append(
                        {
                            'fake-publisher-{}'.format(fake_publisher_name): {'jwks_keys': [jwk_dict]}
                        }
                    )
                else:
                    publisher_keys.append(
                        {
                            '{}'.format(fake_publisher_name): {'jwks_keys': [jwk_dict]}
                        }
                    )
        return publisher_keys

    def _get_oidc_discovery_uri(self):
        return self._config(
            'oidc_discovery_uri', namespace='cis', default='https://auth.mozilla.auth0.com/.well-known/jwks.json'
        ).lower()

    def _get_access_file(self):
        access_file_endpoint = self._config(
            'access_file_endpoint', namespace='cis', default='https://cdn.sso.mozilla.com/apps.yml'
        ).lower()

        access_file_key_content = load_key_file('fake-access-file-key', 'pub')
        jwk_construct = jwk.construct(access_file_key_content, algorithm='RS256')

        dummy_signing_key = jwk_construct.to_dict()

        for k, v in dummy_signing_key.items():
            if isinstance(v, bytes):
                dummy_signing_key[k] = v.decode()

        dummy_signing_key['use'] = 'sig'
        dummy_signing_key['kid'] = uuid4().hex
        dummy_signing_key['x5c'] = 'unsupported'

        access_file_data_structure = {
            'endpoint': access_file_endpoint,
            'aai_mapping': {
                'LOW': ['NO_RECENT_AUTH_FAIL', 'AUTH_RATE_NORMAL'],
                'MEDIUM': ['2FA', 'HAS_KNOWN_BROWSER_KEY'],
                'HIGH': ['GEOLOC_NEAR', 'SAME_IP_RANGE'],
                'MAXIMUM': ['KEY_AUTH']
            },
            'jwks_keys': [
                dummy_signing_key
            ]
        }

        return access_file_data_structure

    def _get_person_api(self):
        person_api_scopes = [
            'write',
            'read',
            'class:public',
            'class:mozilla_confidential',
            'class:workgroup_confidential:staff_only',
        ]

        person_api_data_structure = dict(
            endpoint=self._config(
                'person_api_endpoint', namespace='cis', default=''
            ).lower(),
            profile_schema_combined_uri=self._config(
                'profile_schema_combined_uri', namespace='cis', default=''
            ).lower(),
            profile_core_schema_uri=self._config(
                'profile_core_schema_uri', namespace='cis', default=''
            ).lower(),
            profile_extended_schema_uri=self._config(
                'profile_extended_schema_uri', namespace='cis', default=''
            ).lower(),
            scopes_supported=person_api_scopes
        )

        return person_api_data_structure

    def _get_publishers(self):
        publisher_supported_data_structure = dict()

        for publisher_key in self.publisher_keys:
            publisher_info = self._expand_publisher_key_info(publisher_key)
            publisher_supported_data_structure[
                publisher_info.get('publisher_name')
            ] = publisher_info.get('key_metadata')

        return publisher_supported_data_structure

    def _expand_publisher_key_info(self, publisher_key_dict):
        publisher_name = None
        key_metadata = None
        for k, v in publisher_key_dict.items():
            publisher_name = k
            key_metadata = v

        publisher_key_info = {
            'publisher_name': publisher_name,
            'key_metadata': key_metadata
        }

        return publisher_key_info
