import logging

logger = logging.getLogger(__name__)
logging.basicConfig()


class TestFixture(object):
    def test_object_init(self):
        from cis_fake_well_known import fixture

        f = fixture.Key(
            key_type='priv',
            key_name='fake-publisher-key_0',
            encoded=True
        )

        res = f.material

        assert res is not None

    def test_non_encoded_returns_bytes(self):
        from cis_fake_well_known import fixture

        f = fixture.Key(
            key_type='priv',
            key_name='fake-publisher-key_0',
            encoded=False
        )

        res = f.material

        this_key_type = isinstance(res, bytes)
        assert this_key_type is True

    def test_list_available_keys(self):
        from cis_fake_well_known import fixture
        f = fixture.Key()
        res = f.available_keys()
        assert isinstance(res, list) is True
