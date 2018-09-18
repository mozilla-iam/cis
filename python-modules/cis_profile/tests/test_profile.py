

class TestProfile(object):
    def test_user_init(self):
        from cis_profile import profile

        u = profile.User()
        assert u is not None

    def test_profile_override(self):
        from cis_profile import profile

        u = profile.User(user_id='test')
        assert u.user_id.value == 'test'

    def test_profile_update(self):
        from cis_profile import profile

        u = profile.User()
        old_ts = "1971-09-14T13:41:36.000Z"
        u.user_id.metadata.last_modified = old_ts
        u.user_id.value = 'test'
        u.update_timestamp('user_id')
        assert old_ts != u.user_id.metadata.last_modified

    def test_profile_validation(self):
        from cis_profile import profile
        import jsonschema.exceptions

        u = profile.User()
        u.validate()

        u.user_id.value = {'invalid': 'test'}
        try:
            u.validate()
            raise Exception('ValidationFailure', 'Should have failed validation, did not')
        except jsonschema.exceptions.ValidationError:
            pass
        else:
            raise Exception('ValidationFailure', 'Should have failed validation, did not')

    def test_full_profile_signing(self):
        from cis_profile import profile

        u = profile.User(user_id='test')
        u.sign_all()
        assert u.user_id.signature.publisher.value is not None
        assert len(u.user_id.signature.publisher.value) > 0
        # Empty attributes should not be signed
        assert u.fun_title.value is None

    def test_single_attribute_signing(self):
        from cis_profile import profile

        u = profile.User(user_id='test')
        u.sign_attribute('user_id')
        assert u.user_id.signature.publisher.value is not None
        assert len(u.user_id.signature.publisher.value) > 0

        # Empty attributes should be signed in this case since it's directly requested to be signed
        u.sign_attribute('fun_title')
        assert u.fun_title.signature.publisher.value is not None
        assert len(u.fun_title.signature.publisher.value) > 0

        # test for subitems
        u.sign_attribute('access_information.ldap')
        assert u.access_information.ldap.signature.publisher.value is not None
        assert len(u.access_information.ldap.signature.publisher.value) > 0
