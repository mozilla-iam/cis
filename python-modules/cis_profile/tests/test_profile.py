from cis_profile import profile
from cis_profile.common import MozillaDataClassification
from cis_profile.common import DisplayLevel

import copy
import cis_profile.exceptions
import pytest
import os
import json
import jsonschema


class TestProfile(object):
    def setup(self):
        os.environ["CIS_CONFIG_INI"] = "tests/fixture/mozilla-cis.ini"

    def test_user_init(self):
        u = profile.User()
        j = u.as_json()
        d = u.as_dict()
        assert j is not None
        assert d is not None
        assert u is not None

    def test_filter_scopes(self):
        u = profile.User()
        # Make sure a value is non-public
        u.user_id.metadata.classification = MozillaDataClassification.MOZILLA_CONFIDENTIAL[0]
        u.staff_information.title.metadata.classification = MozillaDataClassification.MOZILLA_CONFIDENTIAL[0]
        u.filter_scopes(MozillaDataClassification.PUBLIC)
        assert "user_id" not in u.as_dict().keys()
        assert "title" not in u.as_dict()["staff_information"].keys()

    def test_filter_display(self):
        u = profile.User()
        # Make sure a value is non-public
        u.user_id.metadata.display = DisplayLevel.STAFF
        u.staff_information.title.metadata.display = DisplayLevel.NULL
        u.filter_scopes(DisplayLevel.PUBLIC)
        assert "user_id" not in u.as_dict().keys()
        assert "title" not in u.as_dict()["staff_information"].keys()

    def test_profile_override(self):
        u = profile.User(user_id="test")
        assert u.user_id.value == "test"

    def test_profile_update(self):
        u = profile.User()
        old_ts = "1971-09-14T13:41:36.000Z"
        u.user_id.metadata.last_modified = old_ts
        u.user_id.value = "test"
        u.update_timestamp("user_id")
        assert old_ts != u.user_id.metadata.last_modified

    def test_profile_validation(self):
        from cis_profile import profile
        import jsonschema.exceptions

        u = profile.User()
        u.validate()

        u.user_id.value = {"invalid": "test"}
        try:
            u.validate()
            raise Exception("ValidationFailure", "Should have failed validation, did not")
        except jsonschema.exceptions.ValidationError:
            pass
        else:
            raise Exception("ValidationFailure", "Should have failed validation, did not")

    def test_full_profile_signing(self):
        u = profile.User(user_id="test")
        u.sign_all(publisher_name="ldap")
        assert u.user_id.signature.publisher.value is not None
        assert len(u.user_id.signature.publisher.value) > 0
        # Empty attributes should not be signed
        assert u.fun_title.value is None

    def test_single_attribute_signing(self):
        u = profile.User(user_id="test")
        u.sign_attribute("user_id", publisher_name="ldap")
        assert u.user_id.signature.publisher.value is not None
        assert len(u.user_id.signature.publisher.value) > 0

        # Empty attributes should be signed in this case since it's directly requested to be signed
        u.sign_attribute("fun_title", publisher_name="ldap")
        assert u.fun_title.signature.publisher.value is not None
        assert len(u.fun_title.signature.publisher.value) > 0

        # test for subitems
        u.sign_attribute("access_information.ldap", publisher_name="ldap")
        assert u.access_information.ldap.signature.publisher.value is not None
        assert len(u.access_information.ldap.signature.publisher.value) > 0

    def test_full_profile_signing_verification(self):
        u = profile.User(user_id="test")
        u.sign_all(publisher_name="ldap")
        u.verify_all_signatures()

    def test_single_attribute_signing_verification(self):
        u = profile.User(user_id="test")
        u.sign_attribute("user_id", publisher_name="ldap")
        u.verify_attribute_signature("user_id")
        with pytest.raises(cis_profile.exceptions.SignatureVerificationFailure):
            u.verify_attribute_signature("fun_title")  # Unsigned, so should raise and fail

    def test_verify_can_publish(self):
        u = profile.User(user_id="test")

        attrfail = copy.deepcopy(u.first_name)
        attrfail["signature"]["publisher"]["name"] = "failure"
        attrfail["value"] = "failure"
        namefail = "first_name"
        assert u.verify_can_publish(u.user_id, "user_id") is True
        with pytest.raises(cis_profile.exceptions.PublisherVerificationFailure):
            u.verify_can_publish(attrfail, namefail)

    def test_verify_all_publishers(self):
        u = profile.User(user_id="test")
        u.verify_all_publishers(u)

        old_user = profile.User()
        old_user.active.value = True
        with pytest.raises(cis_profile.exceptions.PublisherVerificationFailure):
            u.verify_all_publishers(old_user)

    def test_verify_can_publish_login_method(self):
        u = profile.User(login_method="Mozilla-LDAP-Dev")
        u2 = copy.deepcopy(u)
        u2.login_method.value = "github"
        assert u2.verify_all_publishers(u) is True

    def test_data_classification(self):
        u = profile.User(user_id="test")
        assert u.user_id.metadata.classification in MozillaDataClassification.PUBLIC
        assert u.staff_information.worker_type.metadata.classification in MozillaDataClassification.STAFF_ONLY

    def test_json_load_and_self_validate_profile(self):
        profile = json.load(open("cis_profile/data/user_profile_null.json"))
        schema = json.load(open("cis_profile/data/profile.schema"))
        jsonschema.validate(profile, schema)

    def test_merge_profiles(self):
        u_orig = profile.User()
        u_orig.access_information.ldap.values = {"test": None}

        u_patch = profile.User()
        u_patch.access_information.ldap.values = {"test_replacement": None}

        u_orig.merge(u_patch, "ldap")
        assert u_orig.as_dict()["access_information"]["ldap"]["values"] == {"test_replacement": None}
