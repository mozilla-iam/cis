from cis_profile.common import WellKnown


class Test_WellKnown(object):

    def test_wellknown_retrieve(self):
        wk = WellKnown()
        data = wk.get_well_known()
        assert(isinstance(data, dict))
        assert(isinstance(data.get('api'), dict))

    def test_schema_retrieve(self):
        wk = WellKnown()
        data = wk.get_schema()
        assert(isinstance(data, dict))
        assert(isinstance(data.get('$schema'), str))
