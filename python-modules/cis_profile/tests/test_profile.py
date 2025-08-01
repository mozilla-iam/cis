from cis_profile import profile
from cis_profile.common import MozillaDataClassification
from cis_profile.common import DisplayLevel
from unittest import mock

import copy
import cis_profile.exceptions
import pytest
import os
import logging
import json
import jsonschema


logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

logging.getLogger("cis_profile.profile").setLevel(logging.DEBUG)


def _is_or_contains_empty_str(value):
    """Private.
    Determine whether a value is or contains an empty string.
    """

    if value == "":
        return True

    if isinstance(value, list):
        return any([_is_or_contains_empty_str(v) for v in value])

    if isinstance(value, dict):
        return any([_is_or_contains_empty_str(k) or _is_or_contains_empty_str(v) for k, v in value.items()])

    return False


class TestProfile(object):
    def setup(self):
        os.environ["CIS_CONFIG_INI"] = "tests/fixture/mozilla-cis.ini"

    def test_user_init(self):
        u = profile.User()
        j = u.as_json()
        d = u.as_dict()
        ddb = u.as_dynamo_flat_dict()
        assert j is not None
        assert d is not None
        assert u is not None
        assert ddb is not None

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
        u.access_information.ldap.values = {
            "SecurityWiki": None,
            "communitybuild": None,
            "all_scm_level_1": None,
            "active_scm_level_1": None,
            "all_scm_level_3": None,
            "active_scm_level_3": None,
            "active_scm_nss": None,
            "all_scm_sec_sensitive": None,
            "active_scm_sec_sensitive": None,
            "all_scm_level_2": None,
            "active_scm_level_2": None,
            "all_scm_nss": None,
        }
        u.fun_title.value = "test title"
        for _ in ["ldap", "access_provider", "cis", "hris", "mozilliansorg"]:
            u.sign_all(publisher_name=_, safety=False)
        # assert 2 different publisher attributes are signed properly
        assert u.user_id.signature.publisher.value is not None
        assert len(u.user_id.signature.publisher.value) > 0
        assert u.fun_title.signature.publisher.value is not None
        assert len(u.fun_title.signature.publisher.value) > 0
        assert u.access_information.ldap.signature.publisher.value is not None
        # Empty attributes should not be signed
        assert u.last_name.value is None

    def test_full_profile_signing_wrong_publisher(self):
        u = profile.User()
        u.fun_title.value = "test title"
        u.fun_title.signature.publisher.name = "wrong"
        try:
            u.sign_all(publisher_name="ldap")
        except cis_profile.exceptions.SignatureRefused:
            pass
        else:
            raise Exception("ValidationFailure", "Should have failed validation, did not")

    def test_single_attribute_signing(self):
        u = profile.User(user_id="test")
        u.sign_attribute("user_id", publisher_name="ldap")
        assert u.user_id.signature.publisher.value is not None
        assert len(u.user_id.signature.publisher.value) > 0

        # Empty attributes should be signed in this case since it's directly requested to be signed
        # (empty but not None)
        u.fun_title.value = ""
        u.sign_attribute("fun_title", publisher_name="ldap")
        assert u.fun_title.signature.publisher.value is not None
        assert len(u.fun_title.signature.publisher.value) > 0

        # test for subitems
        u.access_information.ldap.values = {"test": None}
        u.sign_attribute("access_information.ldap", publisher_name="ldap")
        assert u.access_information.ldap.signature.publisher.value is not None
        assert len(u.access_information.ldap.signature.publisher.value) > 0

        # test for NULL values
        try:
            u.active.value = None
            u.sign_attribute("active", publisher_name="ldap")
            raise Exception("ValidationFailure", "Should have failed validation, did not")
        except cis_profile.exceptions.SignatureRefused:
            pass
        else:
            raise Exception("ValidationFailure", "Should have failed validation, did not")

    def test_full_profile_signing_verification(self):
        u = profile.User(user_id="test")
        u.access_information.ldap.values = {"test_group": None, "test_group_2": None}
        for _ in ["ldap", "access_provider", "cis", "hris", "mozilliansorg"]:
            u.sign_all(publisher_name=_, safety=False)
        ret = u.verify_all_signatures()
        assert ret is True

    def test_single_attribute_signing_verification(self):
        u = profile.User(user_id="test")
        u.sign_attribute("user_id", publisher_name="ldap")
        ret = u.verify_attribute_signature("user_id")
        assert ret is not None
        with pytest.raises(cis_profile.exceptions.SignatureVerificationFailure):
            u.verify_attribute_signature("fun_title")  # Unsigned, so should raise and fail

    @mock.patch("cis_crypto.secret.AWSParameterstoreProvider.uuid_salt")
    def test_initialize_uuid_and_primary_username(self, mock_salt):
        mock_salt.return_value = "12345"
        u = profile.User(user_id="test")
        u.initialize_uuid_and_primary_username()
        assert u.uuid["value"] is not None
        assert u.uuid["value"] != ""
        assert u.primary_username["value"] is not None
        assert u.primary_username["value"].startswith("r--")

    def test_verify_can_publish(self):
        u_old = profile.User(user_id="test")
        u_new = copy.deepcopy(u_old)

        u_new.first_name["signature"]["publisher"]["name"] = "failure"
        u_new.first_name["value"] = "failure"
        with pytest.raises(cis_profile.exceptions.PublisherVerificationFailure):
            u_new.verify_can_publish(u_new.first_name, "first_name", previous_attribute=u_old.first_name) is True

        assert u_new.verify_can_publish(u_new.user_id, "user_id", previous_attribute=u_old.user_id)

    def test_verify_can_publish_when_merging(self):
        u_orig = profile.User()
        u_orig.access_information.ldap.values = {"test": None}
        u_orig.uuid.value = "31337"
        u_orig.active.value = None
        for _ in ["ldap", "access_provider", "cis", "hris", "mozilliansorg"]:
            u_orig.sign_all(publisher_name=_, safety=False)
        u_patch = profile.User()
        u_patch.access_information.ldap.values = {"test_replacement": None}
        u_orig.merge(u_patch)

        u_orig.verify_all_publishers(u_patch)
        assert u_orig.active.value is None

    def test_verify_all_publishers(self):
        u = profile.User(user_id="test", first_name="tester")
        u.verify_all_publishers(u)

        old_user = profile.User()
        old_user.active.value = True
        old_user.active.signature.publisher.name = "access_provider"
        with pytest.raises(cis_profile.exceptions.PublisherVerificationFailure):
            u.verify_all_publishers(old_user)

        old_user_2 = profile.User()
        old_user_2.first_name.value = "nottest"
        old_user_2.first_name.signature.publisher.name = "mozilliansorg"
        u.first_name.value = "test"
        u.first_name.signature.publisher.name = "access_provider"
        with pytest.raises(cis_profile.exceptions.PublisherVerificationFailure):
            u.verify_all_publishers(old_user_2)

    def test_verify_all_publishers_mozillians_exception(self):
        """
        This tests the whitelisted exception for DinoPark/Mozilliansorg to be allowed to change display or verified
        metadata values, when the actual value/values of the attribute is NOT modified
        """
        u = profile.User(user_id="test", first_name="tester")
        u.first_name.metadata.display = "public"

        old_user = profile.User()
        old_user.first_name.value = "tester"  # same value
        old_user.first_name.metadata.display = "private"  # different display
        old_user.first_name.signature.publisher.name = "access_provider"
        assert u.verify_all_publishers(old_user) is True

    def test_verify_all_publishers_modify_metadata(self):
        u = profile.User(user_id="test", first_name="tester")
        u.user_id.metadata.display = "public"
        u.user_id.signature.publisher.name = "access_provider"

        old_user = profile.User()
        old_user.user_id.value = "test"  # same value
        old_user.user_id.metadata.display = "private"  # different display
        old_user.user_id.signature.publisher.name = u.user_id.signature.publisher.name
        assert u.verify_all_publishers(old_user) is True

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
        u_orig.uuid.value = "31337"

        u_patch = profile.User()
        u_patch.access_information.ldap.values = {"test_replacement": None}

        u_orig.merge(u_patch)
        assert u_orig.as_dict()["access_information"]["ldap"]["values"] == {"test_replacement": None}
        assert u_orig.uuid.value == "31337"  # This has not changed because it was null/None in the patched profile

    def test_merge_return_value(self):
        a = profile.User(user_id="usera")
        b = profile.User(user_id="userb")

        res = a.merge(b)
        assert "user_id" in res

    def test_dynamo_flat_dict(self):
        a = profile.User(user_id="usera")
        ddb = a.as_dynamo_flat_dict()
        # Dict must be flat
        assert ddb["user_id"] is not None
        assert not _is_or_contains_empty_str(ddb)

    def test_dynamo_flat_dict_with_failing_phone(self):
        a = profile.User(user_id="usera")
        a.phone_numbers["values"] = {"foo": ""}
        ddb = a.as_dynamo_flat_dict()
        assert ddb["user_id"] is not None
