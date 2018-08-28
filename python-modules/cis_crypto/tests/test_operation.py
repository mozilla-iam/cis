import json
import os
import pytest

from cis_fake_well_known import app

class TestOperation(object):
    def test_sign_operation(self):
        from cis_crypto import operation
        os.environ['CIS_SECRET_MANAGER_FILE_PATH'] = 'tests/fixture'
        os.environ['CIS_SECRET_MANAGER'] = 'file'
        os.environ['CIS_SIGNING_KEY_NAME'] = 'fake-access-file-key'

        # Taken from the profile v2 specification
        # https://github.com/mozilla-iam/cis/blob/profilev2/docs/profile_data/user_profile_core_plus_extended.json
        """
        {
            'uris': {
                'signature': {
                  'publisher': {
                    'alg': 'RS256',
                    'typ': 'JWT',
                    'value': 'abc'
                  },
                  'additional': [
                    {
                      'alg': 'RS256',
                      'typ': 'JWT',
                      'value': 'abc'
                    }
                  ]
                },
                'metadata': {
                  'classification': 'PUBLIC',
                  'last_modified': '2018-01-01T00:00:00Z',
                  'created': '2018-01-01T00:00:00Z',
                  'publisher_authority': 'mozilliansorg',
                  'verified': 'false'
                },
                'values': {
                  'my blog': 'https://example.net/blog'
                }
            }
        }
        """

        # Assumption : we only want to sign values and not metadata.
        sample_payload = {
            'metadata': {
              'classification': 'PUBLIC',
              'last_modified': '2018-01-01T00:00:00Z',
              'created': '2018-01-01T00:00:00Z',
              'publisher_authority': 'mozilliansorg',
              'verified': 'false'
            },
            'values': {
              'my blog': 'https://example.net/blog'
            }
        }

        o = operation.Sign()
        assert o is not None

        test_valid_payload =  o.load(sample_payload)

        assert test_valid_payload is not None
        assert isinstance(test_valid_payload, dict) is True
        assert isinstance(o.payload, dict) is True

        test_str_payload =  o.load(json.dumps(sample_payload))
        assert isinstance(test_valid_payload, dict) is True
        assert isinstance(o.payload, dict) is True

        signature = o.jws()
        assert isinstance(signature, str) is True


    def test_verify_operation_without_dict(self):
        from cis_crypto import operation
        os.environ['CIS_SECRET_MANAGER_FILE_PATH'] = 'tests/fixture'
        os.environ['CIS_SECRET_MANAGER'] = 'file'
        os.environ['CIS_SIGNING_KEY_NAME'] = 'fake-access-file-key'
        os.environ['CIS_PUBLIC_KEY_NAME'] = 'fake-access-file-key'
        os.environ['CIS_WELL_KNOWN_MODE'] = 'file'



        fh = open('tests/fixture/good-signature')
        fixture_signature = fh.read().rstrip('\n').encode('utf-8')

        o = operation.Verify()
        o.load(fixture_signature)
        key_material = o._get_public_key()
        assert key_material is not None
        res = o.jws()
        assert res is not None

    def test_verify_operation_without_bad_sig(self):
        from cis_crypto import operation
        from jose.exceptions import JWSError

        os.environ['CIS_SECRET_MANAGER_FILE_PATH'] = 'tests/fixture'
        os.environ['CIS_SECRET_MANAGER'] = 'file'
        os.environ['CIS_SIGNING_KEY_NAME'] = 'evil-signing-key'
        os.environ['CIS_PUBLIC_KEY_NAME'] = 'fake-access-file-key'
        os.environ['CIS_WELL_KNOWN_MODE'] = 'file'

        # Assumption : we only want to sign values and not metadata.
        sample_payload = {
            'metadata': {
              'classification': 'PUBLIC',
              'last_modified': '2018-01-01T00:00:00Z',
              'created': '2018-01-01T00:00:00Z',
              'publisher_authority': 'mozilliansorg',
              'verified': 'false'
            },
            'values': {
              'my blog': 'https://example.net/blog'
            }
        }

        s = operation.Sign()
        assert s is not None
        test_valid_payload =  s.load(sample_payload)
        sig = s.jws()

        o = operation.Verify()
        o.load(sig)
        key_material = o._get_public_key()
        assert key_material is not None

        # Expect verification to fail
        with pytest.raises(JWSError):
            res = o.jws()
