

class TestApp(object):
    def test_key_loader(self):
        from cis_fake_well_known.common import load_key_file

        res_1 = load_key_file('fake-publisher-key_1', 'pub')
        assert res_1 is not None

        res_2 = load_key_file('fake-publisher-key_0', 'priv')
        assert res_2 is not None

    def test_encoder_method(self):
        from cis_fake_well_known.common import encode_key

        sample_key_material = '1234567890'
        res = encode_key(sample_key_material)
        assert res is not None

        res = encode_key(sample_key_material.encode())
        assert res is not None
