#!/usr/bin/env python

from cis_profile.common import WellKnown
from cis_profile.common import DotDict
from cis_profile.common import MozillaDataClassification
from cis_profile.common import DisplayLevel

import cis_crypto.operation
import cis_profile.exceptions
import jose.exceptions
import json
import json.decoder
from uuid import uuid5
from uuid import NAMESPACE_URL
from base64 import urlsafe_b64encode
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError


try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError
import jsonschema
import logging
import os
import time

logger = logging.getLogger(__name__)


class User(object):
    """
    A Mozilla IAM Profile "v2" user structure.
    It is loaded a configuration file (JSON) and dynamically generated.
    If you wish to change the structure, modify the JSON file!

    By default this will load the JSON file with its defaults.

    You can use this like a normal class:
    ```
    from cis_profile import User
    skel_user = User(user_id="bobsmith")
    skel_user.user_id.value = "notbobsmith"
    if skel_user.validate():
        profile = skel_user.as_json()
    ```
    """

    def __init__(self, user_structure_json=None, user_structure_json_file=None, discovery_url=None, **kwargs):
        """
        @user_structure_json an existing user structure to load in this class
        @user_structure_json_file an existing user structure to load in this class, from a JSON file
        @discovery_url the well-known Mozilla IAM URL
        @kwargs any user profile attribute name to override on initializing, eg "user_id='test'"
        """
        if discovery_url is None:
            discovery_url = os.environ.get("CIS_DISCOVERY_URL", "https://auth.mozilla.com/.well-known/mozilla-iam")
        self.__well_known = WellKnown(discovery_url)

        if user_structure_json is not None:
            # Auto-detect if the passed struct is a JSON string or JSON dict
            if isinstance(user_structure_json, str):
                self.load(json.loads(user_structure_json))
            else:
                self.load(user_structure_json)
        elif user_structure_json_file is not None:
            self.load(self.get_profile_from_file(user_structure_json_file))
        else:
            # Load builtin defaults
            self.load(self.get_profile_from_file("data/user_profile_null.json"))

        # Insert defaults from kwargs
        for kw in kwargs:
            if kw in self.__dict__.keys():
                try:
                    self.__dict__[kw]["value"] = kwargs[kw]
                except KeyError:
                    self.__dict__[kw]["values"] += [kwargs[kw]]
            else:
                logger.error("Unknown user profile attribute {}".format(kw))
                raise Exception("Unknown user profile attribute {}".format(kw))

        self.__signop = cis_crypto.operation.Sign()
        self.__verifyop = cis_crypto.operation.Verify()
        self.__verifyop.well_known = self.__well_known.get_well_known()

    def load(self, profile_json):
        """
        Load an existing JSON profile
        @profile_json: dict (e.g. from json.load() or json.loads())
        """
        logger.debug("Loading profile JSON data structure into class object")
        self.__dict__.update(DotDict(profile_json))

    def get_profile_from_file(self, user_structure_json_path):
        """
        Load the json structure into a 'DotDict' so that attributes appear as addressable object values
        Usually used with load().
        """
        logger.debug("Loading default profile JSON structure from {}".format(user_structure_json_path))
        if not os.path.isfile(user_structure_json_path):
            dirname = os.path.dirname(os.path.realpath(__file__))
            path = dirname + "/" + user_structure_json_path
        else:
            path = user_structure_json_path
        return DotDict(json.load(open(path)))

    def merge(self, user_to_merge_in, level=None, _internal_level=None):
        """
        Recursively merge user attributes:
        Merge a User object with another User object. This will override all fields from the current user by non-null
        (non-None) fields from `user_to_merge_in`.
        Ex:
        u_orig = User()
        u_patch = User()
        u_patch.timezone.value = "GMT -07:00 America/Los Angeles"
        print(u_patch.uuid.value)
        # >>> None

        u_orig.merge(u_patch)
        print(u_orig.timezone.value)
        # >>> GMT -07:00 America/Los Angeles
        print(u_orig.uuid.value)
        # >>> None # <= unchanged because null/None

        This is useful when updating existing users, rather than manually matching fields

        !!! WARNING !!! This function will not do a validation of signatures or publishers. YOU must perform these tasks
        by calling the appropriate functions.

        @user_to_merge_in User object the user to merge into the current user object
        @level dict of an attribute. This can be user_to_merge_in.__dict__ for the top level (recurses through all
        attributes). The level MUST be from user_to_merge_in, not from the original/current user.
        @_internal_level str attribute name  of previous level attribute from the current user. Used internally.

        This function returns a diff of what was changed and is always successful.
        """
        tomerge = []
        different_attrs = []
        # Default to top level
        if level is None:
            level = user_to_merge_in.__dict__
        if _internal_level is None:
            _internal_level = self.__dict__

        for attr in level.keys():
            # If this is an internal class object, skip it
            if attr.startswith("_") or not isinstance(level[attr], dict):
                continue
            # If we have no signature (or metadata in theory), this is not a "User attribute", keep doing deeper
            if "signature" not in level[attr].keys():
                different_attrs.extend(
                    self.merge(user_to_merge_in, level=level[attr], _internal_level=_internal_level[attr])
                )
            # We will merge this attribute back (granted its not null/None)
            else:
                tomerge.append(attr)

        for attr in tomerge:
            # _internal_level is the original user attr
            # level is the patch/merged in user attr
            # This is where we skip null/None attributes even if the original/current
            # user does not match (ie is not null)
            # What is considered equivalent:
            # Same `value` or `values`
            # Same `metadata.display` or `metadata.verified`
            # Different `signature.*` is ignored if the rest matches (re-signing existing values is ignored)
            # Different `metadata.{last_modified,created,classification}` is ignored if the rest matches
            if level[attr].get("value") is not None or level[attr].get("values") is not None:
                if (_internal_level[attr].get("value") != level[attr].get("value")) or (
                    _internal_level[attr].get("values") != level[attr].get("values")
                    or (_internal_level[attr]["metadata"]["display"] != level[attr]["metadata"]["display"])
                    or (_internal_level[attr]["metadata"]["verified"] != level[attr]["metadata"]["verified"])
                ):
                    logger.debug("Merging in attribute {}".format(attr))
                    different_attrs.append(attr)
                    _internal_level[attr] = level[attr]

        return different_attrs

    def initialize_uuid_and_primary_username(self):
        try:
            salt = cis_crypto.secret.AWSParameterstoreProvider().uuid_salt()
        except ClientError as e:
            logger.critical("No salt set for uuid generation. This is very very dangerous: {}".format(e))
            salt = ""
        now = self._get_current_utc_time()
        uuid = uuid5(NAMESPACE_URL, "{}#{}".format(salt, self.__dict__["user_id"]["value"]))
        self.__dict__["uuid"]["value"] = str(uuid)
        self.__dict__["uuid"]["metadata"]["created"] = now
        self.__dict__["uuid"]["metadata"]["last_modified"] = now
        primary_username = "r--{}".format(urlsafe_b64encode(uuid.bytes).decode("utf-8"))
        self.__dict__["primary_username"]["value"] = primary_username
        self.__dict__["primary_username"]["metadata"]["created"] = now
        self.__dict__["primary_username"]["metadata"]["last_modified"] = now

    def initialize_timestamps(self):
        now = self._get_current_utc_time()
        logger.debug("Setting all profile metadata fields and profile modification timestamps to now: {}".format(now))

        for item in self.__dict__:
            if type(self.__dict__[item]) is not DotDict:
                continue
            if "metadata" in self.__dict__[item]:
                self.__dict__[item]["metadata"]["created"] = now
                self.__dict__[item]["metadata"]["last_modified"] = now
            else:
                # This is a 2nd level attribute such as `access_information`
                # Note that we do not have a 3rd level so this is sufficient
                for subitem in self.__dict__[item]:
                    if isinstance(self.__dict__[item][subitem], dict) and "metadata" in self.__dict__[item][subitem]:
                        self.__dict__[item][subitem]["metadata"]["created"] = now
                        self.__dict__[item][subitem]["metadata"]["last_modified"] = now

        # XXX Hard-coded special profile values
        self.__dict__["last_modified"].value = now
        self.__dict__["created"].value = now

    def update_timestamp(self, req_attr):
        """
        Updates metadata timestamps for that attribute
        @attr a valid user profile attribute
        """
        req_attrs = req_attr.split(".")  # Support subitems/subattributes such as 'access_information.ldap'
        if len(req_attrs) == 1:
            attr = self.__dict__[req_attr]
        else:
            attr = self.__dict__[req_attrs[0]][req_attrs[1]]

        if "metadata" not in attr:
            raise KeyError("This attribute does not have metadata to update")

        now = self._get_current_utc_time()

        logger.debug("Updating to metadata.last_modified={} for attribute {}".format(now, req_attr))
        attr["metadata"]["last_modified"] = now

    def _get_current_utc_time(self):
        """
        returns str of current time that is valid for the CIS user profiles
        """
        # instruct libc that we want UTC
        os.environ["TZ"] = "UTC"
        now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        return now

    def _clean_dict(self):
        """
        Removes non-user-attrs from internal dict
        """
        user = self.__dict__.copy()
        todel = []
        classname = self.__class__.__name__
        for k in user:
            # Anything that is within the class namespace is whitelisted
            if k.startswith("_{}".format(classname)) or k.startswith("_User"):
                todel.append(k)

        for d in todel:
            del user[d]

        return user

    def as_json(self):
        """
        Outputs a JSON version of this user
        Filters out reserved values
        """
        user = self._clean_dict()
        return json.dumps(user)

    def as_dict(self):
        """
        Outputs a real dict version of this user (not a DotDict)
        Filters out reserved values
        """
        user = self._clean_dict()
        return dict(user)

    def as_dynamo_flat_dict(self):
        """
        Flattens out User.as_dict() output into a simple structure without any signature or metadata.
        Effectively, this outputs something like this:
        ```{'uuid': '11c8a5c8-0305-4524-8b41-95970baba84c', 'user_id': 'email|c3cbf9f5830f1358e28d6b68a3e4bf15', ...```
        `flatten()` is recursive.
        Note that this form cannot be verified or validated back since it's missing all attributes!

        Return: dynamodb serialized low level dict of user in a "flattened" form for dynamodb consumption in particular
        """
        user = self._clean_dict()

        def sanitize(attrs):
            # Types whose values need no sanitization to serialize.
            supported_base_types = [type(None), bool, int, float]

            # Empty strings cannot be sanitized.
            def is_nonempty_str(s):
                return isinstance(s, str) and len(s) > 0

            def not_empty_str(v):
                return not isinstance(v, str) or is_nonempty_str(v)

            if type(attrs) in supported_base_types or is_nonempty_str(attrs):
                return attrs

            # We want to remove empty strings from lists and sanitize everything else.
            if isinstance(attrs, list):
                cleaned = filter(not_empty_str, attrs)

                return list(map(sanitize, cleaned))

            # We are dealing with a dictionary.
            cleaned = {
                key: sanitize(value) for key, value in attrs.items() if not_empty_str(key) and not_empty_str(value)
            }

            # If we have a dictionary, we want to ensure it only has one of either
            # the "value" key or "values" key.
            has_value = "value" in cleaned
            has_values = "values" in cleaned

            if (has_value and not has_values) or (has_values and not has_value):
                return cleaned.get("value", cleaned.get("values"))

            return cleaned

        serializer = TypeSerializer()
        return {k: serializer.serialize(v) for k, v in sanitize(user).items()}

    def filter_scopes(self, scopes=MozillaDataClassification.PUBLIC, level=None):
        """
        Filter in place/the current user profile object (self) to only contain attributes with scopes listed in @scopes
        @scopes list of str
        """
        self._filter_all(level=self.__dict__, valid=scopes, check="classification")

    def filter_display(self, display_levels=[DisplayLevel.PUBLIC, DisplayLevel.NULL], level=None):
        """
        Filter in place/the current user profile object (self) to only contain attributes with display levels listed
        in @display_levels
        @display_levels list of str
        """
        self._filter_all(level=self.__dict__, valid=display_levels, check="display")

    def validate(self):
        """
        Validates against a JSON schema
        """

        return jsonschema.validate(self.as_dict(), self.__well_known.get_schema())

    def verify_all_publishers(self, previous_user):
        """
        Verifies all child nodes have an allowed publisher set according to the rules
        @previous_user profile.User object is the previous user we're updating fields from. This allows for checking if
        fields are being updated (value is already set) or created (values are changed from `null`). It defaults to an
        empty profile (with a bunch of `null` values).

        Ex: user.verify_all_publishers(cis_profile.profile.User()) #this checks against a brand new user

        Returns True on success, False if validation fails.
        """
        for item in self.__dict__:
            if type(self.__dict__[item]) is not DotDict:
                continue
            try:
                attr = self.__dict__[item]
                ret = self.verify_can_publish(attr, attr_name=item, previous_attribute=previous_user.as_dict()[item])
            except (AttributeError, KeyError):
                # This is the 2nd level attribute match, see also initialize_timestamps()
                for subitem in self.__dict__[item]:
                    attr = self.__dict__[item][subitem]
                    ret = self.verify_can_publish(
                        attr,
                        attr_name=subitem,
                        parent_name=item,
                        previous_attribute=previous_user.as_dict()[item][subitem],
                    )
            if ret is not True:
                logger.warning("Verification of publisher failed for attribute {}".format(attr))
                return False
        return True

    def verify_can_publish(self, attr, attr_name, parent_name=None, previous_attribute=None):
        """
        Verifies that the selected publisher is allowed to change this attribute.
        This works for both first-time publishers ('created' permission) and subsequent updates ('update' permission).

        Note that this does NOT VERIFY SIGNATURE and that you MUST call verify_attribute_signature()
        separately.

        If you do not, any publisher can pass a fake publisher name and this function will answer that the publisher is
        allowed to publish, if the correct one is passed.
        @attr dict requested attribute to verify the publisher of.
        @attr_name str the name of the requested attribute as we cannot look this up.
        @parent_name str the name of the requested attribute's parent name as we cannot look this up.
        @previous_attribute dict the previous attribute if the user is being updated. If None, the value is always
        considered to be "updated" from the current value stored in self.__dict__. Otherwise, it will check against
        the passed value if it's `null` or set, and consider it "created" if it's `null`, "updated" otherwise. Makes
        sense? Good!

        Return bool True on publisher allowed to publish, raise Exception otherwise.
        """

        # If there was no change made always allow publishing - this also helps if for example:
        # - user contains a "created" attribute
        # - user has an update merged in
        # - any non-updated attribute will pass here (but may otherwise fail because their attribute will be understood
        # as "updated" otherwise
        if attr == previous_attribute:
            logger.debug("Both attribute match and were not modified, allowing to publish (skipped verification logic)")
            return True

        publisher_name = attr.signature.publisher.name  # The publisher that attempts the change is here
        logger.debug("Verifying that {} is allowed to publish field {}".format(publisher_name, attr_name))
        operation = "create"

        # Rules JSON structure:
        # { "create": { "user_id": [ "publisherA", "publisherB"], ...}, "update": { "user_id": "publisherA",... }
        # I know `updators` is not English :)
        # DO NOTE: "create" is a list while "update" is a single item/str (ie check in the list of creators, but check
        # equality against updators). This is because we explicitely do not support multiple update mechanisms, while we
        # do support multiple create mechanisms.
        rules = self.__well_known.get_publisher_rules()
        if parent_name is None:
            allowed_creators = rules["create"][attr_name]
            allowed_updators = rules["update"][attr_name]
        else:
            try:
                allowed_creators = rules["create"][parent_name][attr_name]
            except TypeError:  # This is not access_information, this is identities or staff_information
                allowed_creators = rules["create"][parent_name]
            try:
                allowed_updators = rules["update"][parent_name][attr_name]
            except TypeError:  # This is not access_information, this is identities or staff_information
                allowed_updators = rules["update"][parent_name]

        # Do we have an attribute to check against?
        if previous_attribute is not None:
            # Creators are only allowed if there is no previous value set
            if (self._attribute_value_set(previous_attribute) is False) and (self._attribute_value_set(attr) is True):
                operation = "create"
                if publisher_name in allowed_creators:
                    logger.debug("[create] {} is allowed to publish field {}".format(publisher_name, attr_name))
                    return True
            else:
                operation = "update"
                # Find if the value changed at all, else don't bother checking and allow it. Otherwise, we'd fail when a
                # publisher tries to validate all fields, but has not actually modified them all.
                # Figure out where values are stored first:
                if "value" in attr:
                    value = "value"
                else:
                    value = "values"

                if attr[value] == previous_attribute[value]:
                    logger.debug(
                        "[noop] {} skipped verification for  {} (no changes)".format(publisher_name, attr_name)
                    )
                    return True
                elif publisher_name == allowed_updators:
                    logger.debug("[update] {} is allowed to publish field {}".format(publisher_name, attr_name))
                    return True

        # No previous attribute set, just check we're allowed to change the field
        else:
            if not self._attribute_value_set(attr):
                operation = "create"
                logger.debug("[create] {} is allowed to publish field {}".format(publisher_name, attr_name))
                return True
            elif publisher_name == allowed_updators:
                logger.debug("[update] {} is allowed to publish field {}".format(publisher_name, attr_name))
                return True
            else:
                logger.warning(
                    "[noop] no previous_attribute passed, but trying to to compare against an existing value"
                    "({}, {})".format(publisher_name, attr_name)
                )
                raise ValueError("previous_attribute must be set when calling this function, if updating an attribute")

        # None of the checks allowed this change, bail!
        logger.warning(
            "[{}] {} is NOT allowed to publish field {} (value: {}, previous_attribute value: {})".format(
                operation, publisher_name, attr_name, attr, previous_attribute
            )
        )
        raise cis_profile.exceptions.PublisherVerificationFailure(
            "[{}] {} is NOT allowed to publish field {}".format(operation, publisher_name, attr_name)
        )

    def verify_all_signatures(self):
        """
        Verifies all child nodes with a non-null value's signature against a publisher signature
        """
        for item in self.__dict__:
            if type(self.__dict__[item]) is not DotDict:
                continue
            try:
                attr = self.__dict__[item]
                if self._attribute_value_set(attr):
                    logger.debug("Verifying attribute {}".format(item))
                    attr = self._verify_attribute_signature(attr)
            except KeyError:
                # This is the 2nd level attribute match, see also initialize_timestamps()
                for subitem in self.__dict__[item]:
                    attr = self.__dict__[item][subitem]
                    if self._attribute_value_set(attr):
                        logger.debug("Verifying attribute {}.{}".format(item, subitem))
                        attr = self._verify_attribute_signature(attr)
            if attr is None:
                logger.warning("Verification failed for attribute {}".format(attr))
                return False
        return True

    def verify_attribute_signature(self, req_attr):
        """
        Verify the signature of an attribute
        @req_attr str this is this user's attribute name, which will be looked up and verified in place
        """
        req_attrs = req_attr.split(".")  # Support subitems/subattributes such as 'access_information.ldap'
        if len(req_attrs) == 1:
            attr = self.__dict__[req_attr]
        else:
            attr = self.__dict__[req_attrs[0]][req_attrs[1]]
        return self._verify_attribute_signature(attr)

    def _verify_attribute_signature(self, attr, publisher_name=None):
        """
        Verify the signature of an attribute
        @attr dict a structure of this user to be verified
        @publisher_name str this is the name of the publisher that should be signing this attribute. If None, the
        publisher_name from the current user structure is used instead and no check is performed.
        """

        if not self._attribute_value_set(attr):
            logger.error(
                "Disallowing verification of NULL (None) value(s) attribute: {} for publisher {}".format(
                    attr, publisher_name
                )
            )
            raise cis_profile.exceptions.SignatureVerificationFailure("Cannot verify attribute with NULL value(s)")
        if publisher_name is not None and attr["signature"]["publisher"]["name"] != publisher_name:
            raise cis_profile.exceptions.SignatureVerificationFailure("Incorrect publisher")
        else:
            # If publisher name is not passed, we default to the attribute's built-in publisher
            publisher_name = attr["signature"]["publisher"]["name"]

        logger.debug(
            "Attempting signature verification for publisher: {} and attribute: {}".format(publisher_name, attr)
        )
        self.__verifyop.load(attr["signature"]["publisher"]["value"])
        try:
            signed = json.loads(self.__verifyop.jws(publisher_name))
        except jose.exceptions.JWSError as e:
            logger.warning("Attribute signature verification failure: {} ({})".format(attr, publisher_name))
            raise cis_profile.exceptions.SignatureVerificationFailure(
                "Attribute signature verification failure for {}" "({}) ({})".format(attr, publisher_name, e)
            )

        # Finally check our object matches the stored data
        attrnosig = attr.copy()
        del attrnosig["signature"]

        if signed is None:
            raise cis_profile.exceptions.SignatureVerificationFailure(
                "No data returned by jws() call for " "attribute {}".format(attr)
            )
        elif signed != attrnosig:
            raise cis_profile.exceptions.SignatureVerificationFailure(
                "Signature data in jws does not match " "attribute data => {} != {}".format(attrnosig, signed)
            )
        return attr

    def sign_all(self, publisher_name, safety=True):
        """
        Sign all child nodes with a non-null value(s) OR empty values (strict=False)
        This requires cis_crypto to be properly setup (i.e. with keys)
        To sign empty values, manually call sign_attribute()

        @publisher_name str a publisher name (will be set in signature.publisher.name at signing time)
        @safety bool if off will not raise a SignatureRefused error when your publisher_name does not match (will not
        sign either!)
        """

        logger.debug("Signing all profile fields that have a value set with publisher {}".format(publisher_name))
        for item in self.__dict__:
            if type(self.__dict__[item]) is not DotDict:
                continue
            try:
                attr = self.__dict__[item]
                if self._attribute_value_set(attr, strict=True):
                    if attr["signature"]["publisher"]["name"] == publisher_name:
                        logger.debug("Signing attribute {}".format(item))
                        attr = self._sign_attribute(attr, publisher_name)
                    else:
                        logger.error(
                            "Attribute has value set but wrong publisher set, cannot sign: {} (publisher: {})".format(
                                attr, publisher_name
                            )
                        )
                        if safety:
                            raise cis_profile.exceptions.SignatureRefused(
                                "Attribute has value set but wrong publisher set, cannot" " sign", attr
                            )
            except KeyError:
                # This is the 2nd level attribute match, see also initialize_timestamps()
                for subitem in self.__dict__[item]:
                    attr = self.__dict__[item][subitem]
                    if self._attribute_value_set(attr, strict=True):
                        if attr["signature"]["publisher"]["name"] == publisher_name:
                            logger.debug("Signing attribute {}.{}".format(item, subitem))
                            attr = self._sign_attribute(attr, publisher_name)
                        else:
                            logger.error(
                                "Attribute has value set but wrong publisher set, cannot sign: {} (publisher: "
                                "{})".format(attr, publisher_name)
                            )
                            if safety:
                                raise cis_profile.exceptions.SignatureRefused(
                                    "Attribute has value set but wrong publisher set, cannot" " sign", attr
                                )

    def sign_attribute(self, req_attr, publisher_name):
        """
        Sign a single attribute, including null/empty/unset attributes
        @req_attr str this user's attribute to sign in place
        @publisher_name str a publisher name (will be set in signature.publisher.name) which corresponds to the
        signing key
        """
        req_attrs = req_attr.split(".")  # Support subitems/subattributes such as 'access_information.ldap'
        if len(req_attrs) == 1:
            attr = self.__dict__[req_attr]
        else:
            attr = self.__dict__[req_attrs[0]][req_attrs[1]]
        return self._sign_attribute(attr, publisher_name)

    def _attribute_value_set(self, attr, strict=True):
        """
        Checks if an attribute is used/set, ie not null
        @attr dict a complete CIS Profilev2 attribute (such as {'test': {'value': null}})
        @strict bool if True then only null values will be ignored, if False then empty strings/Lists/Dicts will also be
        ignored
        returns: True if the attribute has a value, False if not
        """

        # Note that None is the JSON `null` equivalent (and not "null" is not the string "null")
        if "value" in attr:
            if attr["value"] is None:
                return False
            elif isinstance(attr["value"], bool):
                return True
            elif not strict and len(attr["value"]) == 0:
                return False
        elif "values" in attr:
            if attr["values"] is None:
                return False
            elif not strict and len(attr["values"]) == 0:
                return False
        else:
            raise KeyError("Did not find value in attribute", attr)
        return True

    def _sign_attribute(self, attr, publisher_name):
        """
        Perform the actual signature operation
        See also https://github.com/mozilla-iam/cis/blob/profilev2/docs/Profiles.md
        @attr: a CIS Profilev2 attribute
        @publisher_name str a publisher name (will be set in signature.publisher.name) which corresponds to the
        signing key
        This method will not allow signing NULL (None) attributes
        """
        if not self._attribute_value_set(attr):
            logger.error(
                "Disallowing signing of NULL (None) value(s) attribute: {} for publisher {}".format(
                    attr, publisher_name
                )
            )
            raise cis_profile.exceptions.SignatureRefused("Signing NULL (None) attribute is forbidden")
        logger.debug("Will sign {} for publisher {}".format(attr, publisher_name))
        # Extract the attribute without the signature structure itself
        attrnosig = attr.copy()
        del attrnosig["signature"]
        self.__signop.load(attrnosig)

        # Add the signed attribute back to the original complete attribute structure (with the signature struct)
        # This ensure we also don't touch any existing non-publisher signatures
        sigattr = attr["signature"]["publisher"]
        sigattr["name"] = publisher_name
        sigattr["alg"] = "RS256"  # Currently hardcoded in cis_crypto
        sigattr["typ"] = "JWS"  # ""
        sigattr["value"] = self.__signop.jws(publisher_name)
        return attr

    def _filter_all(self, level, valid, check):
        """
        Recursively filters out (i.e. deletes) attribute values.
        @level dict of an attribute. This can be self.__dict__ for the top level (recurses through all attributes)
        @valid list of valid attributes values, i.e. attribute values that will be retained
        @check str the attribute to check
        """
        todel = []
        for attr in level.keys():
            if attr.startswith("_") or not isinstance(level[attr], dict):
                continue
            if "metadata" not in level[attr].keys():
                self._filter_all(valid=valid, level=level[attr], check=check)
            elif level[attr]["metadata"][check] not in valid:
                todel.append(attr)

        for _ in todel:
            logger.debug("Removing attribute {} because it's not in {}".format(_, valid))
            del level[_]
