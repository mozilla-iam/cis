from cis_profile import profile
from cis_profile.common import MozillaDataClassification

import cis_profile.exceptions
import pytest
import os


class TestProfile(object):
    def setup(self):
        os.environ['CIS_CONFIG_INI'] = 'tests/fixture/mozilla-cis.ini'

    def test_user_init(self):
        u = profile.User()
        assert u is not None

    def test_filter_scopes(Self):
        u = profile.User()
        # Make sure a value is non-public
        u.user_id.metadata.classification = MozillaDataClassification.MOZILLA_CONFIDENTIAL[0]
        u.filter_scopes(MozillaDataClassification.PUBLIC)
        assert(MozillaDataClassification.MOZILLA_CONFIDENTIAL[0] not in u.__dict__)

    def test_profile_override(self):
        u = profile.User(user_id='test')
        assert u.user_id.value == 'test'

    def test_profile_update(self):
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
        u = profile.User(user_id='test')
        u.sign_all()
        assert u.user_id.signature.publisher.value is not None
        assert len(u.user_id.signature.publisher.value) > 0
        # Empty attributes should not be signed
        assert u.fun_title.value is None

    def test_single_attribute_signing(self):
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

    def test_full_profile_signing_verification(self):
        u = profile.User(user_id='test')
        u.sign_all()
        u.verify_all_signatures()

    def test_single_attribute_signing_verification(self):
        u = profile.User(user_id='test')
        u.sign_attribute('user_id')
        u.verify_attribute_signature('user_id')
        u.verify_attribute_signature('user_id', publisher_name='access_provider')
        with pytest.raises(cis_profile.exceptions.SignatureVerificationFailure):
            u.verify_attribute_signature('fun_title')  # Unsigned, so should raise and fail

    def test_verify_can_publish(self):
        u = profile.User(user_id='test')
        publisher_name = 'cis'
        attr = u.user_id.copy()
        name = 'user_id'

        attrfail = u.first_name.copy()
        attrfail['signature']['publisher']['name'] = 'failure'
        namefail = 'first_name'
        assert u.verify_can_publish(name, attr, publisher_name) is True
        with pytest.raises(cis_profile.exceptions.PublisherVerificationFailure):
            u.verify_can_publish(namefail, attrfail, publisher_name)
