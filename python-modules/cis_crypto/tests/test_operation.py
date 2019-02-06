import json
import os
import pytest

logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)


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

    def test_sign_verify_operation_jwks(self):
        # This test is a sign + verify operation with fake local keys ("full chain" test)
        from cis_crypto import operation
        from jose import jwk
        import json

        os.environ["CIS_PUBLIC_KEY_NAME"] = "publisher"
        with open("tests/fixture/fake-well-known.json") as fd:
            fake_wk = json.loads(fd.read())

        with open("tests/fixture/fake-publisher-key_0.priv.jwk") as fd:
            fake_jwk_priv = json.loads(fd.read())
            fake_jwk_priv_jose = jwk.construct(fake_jwk_priv, "RS256")

        # Note: does not include the signature object
        sample_payload = {
            "metadata": {
                "classification": "PUBLIC",
                "last_modified": "1970-01-01T00:00:00Z",
                "created": "1970-01-01T00:00:00Z",
                "verified": True,
                "display": "public",
            },
            "value": "test",
        }

        o = operation.Sign()
        test_valid_payload = o.load(sample_payload)
        assert isinstance(test_valid_payload, dict) is True
        o._jwk = fake_jwk_priv_jose
        signature = o.jws()
        assert isinstance(signature, str) is True

        # verify
        o2 = operation.Verify()
        test_valid_payload["signature"] = {
            "publisher": {"alg": "RS256", "typ": "JWS", "name": "hris", "value": signature}
        }
        o2.well_known_mode = "https"
        o2.well_known = fake_wk
        o2.load(test_valid_payload["signature"]["publisher"]["value"])
        sig = o2.jws(keyname="hris")
        jsig = json.loads(sig)
        assert isinstance(jsig, dict) is True

    def test_jwks_verification(self):
        # This jws sig is signed with the allizom.org mozilliansorg publisher key
        # It uses a copy of the dev well-known
        from cis_crypto import operation

        jws_signature = (
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJtZXRhZGF0YSI6eyJjbGFzc2lmaWNhdGlvbiI6IlBVQkxJQyIsImxhc3R"
            "fbW9kaWZpZWQiOiIyMDE5LTAyLTA1VDEyOjExOjUyLjAwMFoiLCJjcmVhdGVkIjoiMjAxOS0wMi0wNVQxMjoxMTo1Mi4wMDBa"
            "IiwidmVyaWZpZWQiOnRydWUsImRpc3BsYXkiOiJwdWJsaWMifSwidmFsdWUiOiJhOTg2MTM1My1jODRkLTQ5NTktOWI4Ni04ZTA"
            "xZTBmZDQ1MmIifQ.aFzcm6rq1AaOpUymvZkzvDNwVLaQsaVakUrw_VZilXHuY9WwZAC1mXd0pPoZpjeeQY9kq7pWsCwVe5PkBu7_6Yf"
            "EcToKbkpPlID3EmW2qeUIbby7GpiAT1Alnj0PWcfOH_P1E8_DLh7quwOhu8SA1ekmAME6ty0OCd7o6QUUrY4eVozFux2qAFpDd6Oqo-H"
            "K2dkFxRbLZivEZFzAURHN8G7EN3bzicI72R_QDDO_rBEa_QSMmkkhs3M9DB3hBAgzRExNah0NHH6mpcuQl9QnMocR2Moj_pmbKJhpr6wZ"
            "uoTidZyW_sX5ZG5guja7FkwK960yLlwl1AgCXzMUlJ5zZqwuuiWCV5n8f3Cbwd-IUQaiTklAJWunydqcxM32LRUfJ7kR16D2O7LkQf96Z"
            "KBgyH-YyRflFuYtjL6PEmCETOYTJ58m8y4BTWlXicWCv0w7R8tGIQ0AOjdUYh0wIBAvnL_dV2UeENc2f4hrcK_OgDynYeYixVOH-lb0E"
            "QRm2-x-xcVc3aco6W80Z0GooTKT40TYffyt6rEhg0og4cluPX9IQGdd5PD9QfKh5ecoECUQ0nhGNUkAMlqC-bPMgT2a2kxd04p-gZuV"
            "re-laBVWh6NnRird-11fncRyMhJ8HSaZr1ETLzOegR7cFQ5DZhWKAuvcjpBayWUJ2Y1qq4Begjk"
        )
        os.environ["CIS_PUBLIC_KEY_NAME"] = "publisher"
        o = operation.Verify()
        o.load(jws_signature)
        o.well_known_mode = "https"

        fh = open("tests/fixture/well-known.json")
        o.well_known = json.loads(fh.read())
        fh.close()

        key_material = o._get_public_key(keyname="mozilliansorg")
        assert key_material is not None
        res = json.loads(o.jws(keyname="mozilliansorg"))
        assert isinstance(res, dict) is True
