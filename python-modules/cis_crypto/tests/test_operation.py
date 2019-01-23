import json
import mock
import os
import pytest


class TestOperation(object):
    def test_sign_operation_benchmark(self):
        from cis_crypto import operation
        import time

        os.environ["CIS_SECRET_MANAGER_FILE_PATH"] = "tests/fixture"
        os.environ["CIS_SECRET_MANAGER"] = "file"
        os.environ["CIS_SIGNING_KEY_NAME"] = "fake-access-file-key.priv.pem"

        sample_payload = {"values": {"test_key": "test_data"}}

        o = operation.Sign()
        o.load(sample_payload)
        i = 0
        # Run 10 sign operations and average them for accuracy
        start = time.time()
        for i in range(0, 10):
            o.jws()
        stop = time.time()
        taken = stop - start
        taken_per_sig = taken / 10
        print(
            "test_sign_operation_benchmark() has taken {} seconds to run, or {} second per "
            "Sign operation".format(taken, taken_per_sig)
        )
        # On a recent ULV laptop (2018) taken_per_sig is 0.006s, thus we're being very conservative here in case CI is
        # slow, but this would catch anything crazy slow
        assert taken_per_sig < 1

    def test_sign_operation(self):
        from cis_crypto import operation

        os.environ["CIS_SECRET_MANAGER_FILE_PATH"] = "tests/fixture"
        os.environ["CIS_SECRET_MANAGER"] = "file"
        os.environ["CIS_SIGNING_KEY_NAME"] = "fake-access-file-key.priv.pem"

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
            "metadata": {
                "classification": "PUBLIC",
                "last_modified": "2018-01-01T00:00:00Z",
                "created": "2018-01-01T00:00:00Z",
                "publisher_authority": "mozilliansorg",
                "verified": "false",
            },
            "values": {"my blog": "https://example.net/blog"},
        }

        o = operation.Sign()
        assert o is not None

        test_valid_payload = o.load(sample_payload)

        assert test_valid_payload is not None
        assert isinstance(test_valid_payload, dict) is True
        assert isinstance(o.payload, dict) is True

        test_str_payload = o.load(json.dumps(sample_payload))
        assert test_str_payload is not None
        assert isinstance(test_valid_payload, dict) is True
        assert isinstance(o.payload, dict) is True

        signature = o.jws()
        assert isinstance(signature, str) is True

    def test_verify_operation_without_dict(self):
        from cis_crypto import operation

        os.environ["CIS_SECRET_MANAGER_FILE_PATH"] = "tests/fixture"
        os.environ["CIS_SECRET_MANAGER"] = "file"
        os.environ["CIS_SIGNING_KEY_NAME"] = "fake-access-file-key.priv.pem"
        os.environ["CIS_PUBLIC_KEY_NAME"] = "fake-access-file-key.pub.pem"
        os.environ["CIS_WELL_KNOWN_MODE"] = "file"

        fh = open("tests/fixture/good-signature")
        fixture_signature = fh.read().rstrip("\n").encode("utf-8")

        o = operation.Verify()
        o.load(fixture_signature)
        key_material = o._get_public_key()
        assert key_material is not None
        res = o.jws()
        assert res is not None

    def test_verify_operation_without_bad_sig(self):
        from cis_crypto import operation
        from jose.exceptions import JWSError

        os.environ["CIS_SECRET_MANAGER_FILE_PATH"] = "tests/fixture"
        os.environ["CIS_SECRET_MANAGER"] = "file"
        os.environ["CIS_SIGNING_KEY_NAME"] = "evil-signing-key.priv.pem"
        os.environ["CIS_PUBLIC_KEY_NAME"] = "fake-access-file-key.pub.pem"
        os.environ["CIS_WELL_KNOWN_MODE"] = "file"

        # Assumption : we only want to sign values and not metadata.
        sample_payload = {
            "metadata": {
                "classification": "PUBLIC",
                "last_modified": "2018-01-01T00:00:00Z",
                "created": "2018-01-01T00:00:00Z",
                "publisher_authority": "mozilliansorg",
                "verified": "false",
            },
            "values": {"my blog": "https://example.net/blog"},
        }

        s = operation.Sign()
        assert s is not None
        test_valid_payload = s.load(sample_payload)
        assert test_valid_payload is not None
        sig = s.jws()

        o = operation.Verify()
        o.load(sig)
        key_material = o._get_public_key()
        assert key_material is not None

        # Expect verification to fail
        with pytest.raises(JWSError):
            o.jws()

    def _mock_response(self, status=200, content="CONTENT", json_data=None, raise_for_status=None):
        """
        since we typically test a bunch of different
        requests calls for a service, we are going to do
        a lot of mock responses, so its usually a good idea
        to have a helper function that builds these things
        """
        mock_resp = mock.Mock()
        # mock raise_for_status call w/optional error
        mock_resp.raise_for_status = mock.Mock()
        if raise_for_status:
            mock_resp.raise_for_status.side_effect = raise_for_status
        # set status code and content
        mock_resp.status_code = status
        mock_resp.content = content
        # add json data if provided
        if json_data:
            mock_resp.json = mock.Mock(return_value=json_data)
        return mock_resp
