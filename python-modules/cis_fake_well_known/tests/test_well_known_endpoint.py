import logging
import os

logger = logging.getLogger(__name__)
logging.basicConfig()


class TestWellKnownEndpoint(object):
    def test_data_structure_is_complete(self):
        from cis_fake_well_known import well_known
        os.environ['CIS_CONFIG_INI'] = 'tests/mozilla-cis-testing.ini'

        well_known_object = well_known.MozillIAM()

        res = well_known_object.data()

        assert res.get('publishers_supported') is not None
        assert res.get('oidc_discovery_uri') is not None
        assert res.get('access_file') is not None
        assert res.get('person_api') is not None
