#!/usr/bin/env python

from cis_profile.common import WellKnown
from cis_profile.common import DotDict
from cis_profile.common import MozillaDataClassification

import cis_crypto.operation
import cis_profile.exceptions
import jose.exceptions
import json
import json.decoder
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

    def __init__(self, user_structure_json=None, user_structure_json_file=None,
                 discovery_url='https://auth.mozilla.com/.well-known/mozilla-iam', **kwargs):
        """
        @user_structure_json an existing user structure to load in this class
        @user_structure_json_file an existing user structure to load in this class, from a JSON file
        @discovery_url the well-known Mozilla IAM URL
        @kwargs any user profile attribute name to override on initializing, eg "user_id='test'"
        """
        self.__well_known = WellKnown()

        if (user_structure_json is not None):
            self.load(user_structure_json)
        elif (user_structure_json_file is not None):
            self.load(self.get_profile_from_file(user_structure_json_file))
        else:
            # Load builtin defaults
            self.load(self.get_profile_from_file('data/user_profile_null.json'))

        # Insert defaults from kwargs
        for kw in kwargs:
            if kw in self.__dict__.keys():
                try:
                    self.__dict__[kw]['value'] = kwargs[kw]
                except KeyError:
                    self.__dict__[kw]['values'] += [kwargs[kw]]
            else:
                logger.error('Unknown user profile attribute {}'.format(kw))
                raise Exception('Unknown user profile attribute {}'.format(kw))

        self.__signop = cis_crypto.operation.Sign()
        self.__verifyop = cis_crypto.operation.Verify()
        self.__verifyop.well_known = self.__well_known.get_well_known()

    def load(self, profile_json):
        """
        Load an existing JSON profile
        @profile_json: dict (e.g. from json.load() or json.loads())
        """
        logger.debug('Loading profile JSON data structure into class object')
        self.__dict__.update(DotDict(profile_json))

    def get_profile_from_file(self, user_structure_json_path):
        """
        Load the json structure into a 'DotDict' so that attributes appear as addressable object values
        Usually used with load().
        """
        logger.debug('Loading default profile JSON structure from {}'.format(user_structure_json_path))
        if not os.path.isfile(user_structure_json_path):
            dirname = os.path.dirname(os.path.realpath(__file__))
            path = dirname + '/' + user_structure_json_path
        else:
            path = user_structure_json_path
        return DotDict(json.load(open(path)))

    def initialize_timestamps(self):
        # instruct libc that we want UTC
        os.environ['TZ'] = 'UTC'

        now = time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        logger.debug('Setting all profile metadata fields and profile modification timestamps to now: {}'.format(now))

        for item in self.__dict__:
            if type(self.__dict__[item]) is not DotDict:
                continue
            if 'metadata' in self.__dict__[item]:
                self.__dict__[item]['metadata']['created'] = now
                self.__dict__[item]['metadata']['last_modified'] = now
            else:
                # This is a 2nd level attribute such as `access_information`
                # Note that we do not have a 3rd level so this is sufficient
                for subitem in self.__dict__[item]:
                    if isinstance(self.__dict__[item][subitem], dict) and 'metadata' in self.__dict__[item][subitem]:
                        self.__dict__[item][subitem]['metadata']['created'] = now
                        self.__dict__[item][subitem]['metadata']['last_modified'] = now

        # XXX Hard-coded special profile values
        self.__dict__['last_modified'].value = now
        self.__dict__['created'].value = now

    def update_timestamp(self, req_attr):
        """
        Updates metadata timestamps for that attribute
        @attr a valid user profile attribute
        """
        req_attrs = req_attr.split('.')  # Support subitems/subattributes such as 'access_information.ldap'
        if len(req_attrs) == 1:
            attr = self.__dict__[req_attr]
        else:
            attr = self.__dict__[req_attrs[0]][req_attrs[1]]

        if 'metadata' not in attr:
            raise KeyError("This attribute does not have metadata to update")

        # instruct libc that we want UTC
        os.environ['TZ'] = 'UTC'
        now = time.strftime('%Y-%m-%dT%H:%M:%S.000Z')

        logger.debug('Updating to metadata.last_modified={} for attribute {}'.format(now, req_attr))
        attr['metadata']['last_modified'] = now

    def _clean_dict(self):
        """
        Removes non-user-attrs from internal dict
        """
        user = self.__dict__.copy()
        todel = []
        classname = self.__class__.__name__
        for k in user:
            # Anything that is within the class namespace is whitelisted
            if k.startswith('_{}'.format(classname)) or k.startswith('_User'):
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

    def filter_scopes(self, scopes=MozillaDataClassification.PUBLIC):
        """
        Filter in place/the current user profile object (self) to only contain attributes with scopes listed in @scopes
        @scopes list of str
        """
        todel = []
        classname = self.__class__.__name__
        for attr in self.__dict__:
            if attr.startswith('_{}'.format(classname)):
                # Don't touch private attrs
                continue
            elif 'metadata' not in self.__dict__[attr]:
                logger.debug('Attribute {} has no metadata, won\'t filter scopes on it'.format(attr))
                continue
            if self.__dict__[attr]['metadata']['classification'] not in scopes:
                todel.append(attr)

        for d in todel:
            logger.debug('Removing attribute {} because it\'s not in {} scopes'.format(attr, scopes))
            del self.__dict__[d]

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
                    ret = self.verify_can_publish(attr,
                                                  attr_name=item,
                                                  previous_attribute=previous_user.as_dict()[item])
                except (AttributeError, KeyError):
                    # This is the 2nd level attribute match, see also initialize_timestamps()
                    for subitem in self.__dict__[item]:
                        attr = self.__dict__[item][subitem]
                        ret = self.verify_can_publish(attr,
                                                      attr_name=subitem,
                                                      parent_name=item,
                                                      previous_attribute=previous_user.as_dict()[item][subitem])
                if ret is not True:
                    logger.warning('Verification of publisher failed for attribute {}'.format(attr))
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
        publisher_name = attr.signature.publisher.name  # The publisher that attempts the change is here
        logger.debug('Verifying that {} is allowed to publish field {}'.format(publisher_name, attr_name))
        operation = 'create'

        # Rules JSON structure:
        # { "create": { "user_id": [ "publisherA", "publisherB"], ...}, "update": { "user_id": "publisherA",... }
        # I know `updators` is not English :)
        # DO NOTE: "create" is a list while "update" is a single item/str (ie check in the list of creators, but check
        # equality against updators). This is because we explicitely do not support multiple update mechanisms, while we
        # do support multiple create mechanisms.
        rules = self.__well_known.get_publisher_rules()
        if parent_name is None:
            allowed_creators = rules['create'][attr_name]
            allowed_updators = rules['update'][attr_name]
        else:
            try:
                allowed_creators = rules['create'][parent_name][attr_name]
                allowed_updators = rules['update'][parent_name][attr_name]
            except TypeError:  # This is not access_information, this is identities or staff_information
                allowed_creators = rules['create'][parent_name]
                allowed_updators = rules['create'][parent_name]

        # Do we have an attribute to check against?
        if previous_attribute is not None:
            # Creators are only allowed if there is no previous value set
            if (self._attribute_value_set(previous_attribute) is False) and (self._attribute_value_set(attr) is True):
                operation = 'create'
                if publisher_name in allowed_creators:
                    logger.debug('[create] {} is allowed to publish field {}'.format(publisher_name, attr_name))
                    return True
            else:
                operation = 'update'
                # Find if the value changed at all, else don't bother checking and allow it. Otherwise, we'd fail when a
                # publisher tries to validate all fields, but has not actually modified them all.
                # Figure out where values are stored first:
                if 'value' in attr:
                    value = 'value'
                else:
                    value = 'values'

                if attr[value] == previous_attribute[value]:
                    logger.debug('[noop] {} skipped verification for  {} (no changes)'
                                 .format(publisher_name, attr_name))
                    return True
                elif publisher_name == allowed_updators:
                    logger.debug('[update] {} is allowed to publish field {}'.format(publisher_name, attr_name))
                    return True

        # No previous attribute set, just check we're allowed to change the field
        else:
            if not self._attribute_value_set(attr):
                operation = 'create'
                logger.debug('[create] {} is allowed to publish field {}'.format(publisher_name, attr_name))
                return True
            elif publisher_name == allowed_updators:
                logger.debug('[update] {} is allowed to publish field {}'.format(publisher_name, attr_name))
                return True

        # None of the checks allowed this change, bail!
        logger.warning('[{}] {} is NOT allowed to publish field {} (value: {}, previous_attribute value: {})'
                       .format(operation, publisher_name, attr_name, attr, previous_attribute))
        raise cis_profile.exceptions.PublisherVerificationFailure('[{}] {} is NOT allowed to publish field {}'
                                                                  .format(operation, publisher_name, attr_name))

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
                        attr = self._verify_attribute_signature(attr)
                except KeyError:
                    # This is the 2nd level attribute match, see also initialize_timestamps()
                    for subitem in self.__dict__[item]:
                        attr = self.__dict__[item][subitem]
                        if self._attribute_value_set(attr):
                            attr = self._verify_attribute_signature(attr)
                if attr is not True:
                    logger.warning('Verification failed for attribute {}'.format(attr))
                    return False
        return True

    def verify_attribute_signature(self, req_attr):
        """
        Verify the signature of an attribute
        @req_attr str this is this user's attribute name, which will be looked up and verified in place
        """
        req_attrs = req_attr.split('.')  # Support subitems/subattributes such as 'access_information.ldap'
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

        if publisher_name is not None and attr['signature']['publisher']['value'] != publisher_name:
            raise cis_profile.exceptions.SignatureVerificationFailure('Incorrect publisher')

        self.__verifyop.load(attr['signature']['publisher']['value'])
        try:
            signed = json.loads(self.__verifyop.jws(publisher_name))
        except jose.exceptions.JWSError as e:
            logger.warning('Attribute signature verification failure: {} ({})'.format(attr, publisher_name))
            raise cis_profile.exceptions.SignatureVerificationFailure('Attribute signature verification failure for {}'
                                                                      '({}) ({})'.format(attr, publisher_name, e))

        # Finally check our object matches the stored data
        attrnosig = attr.copy()
        del attrnosig['signature']

        if signed is None:
            raise cis_profile.exceptions.SignatureVerificationFailure('No data returned by jws() call for '
                                                                      'attribute {}'.format(attr))
        elif signed != attrnosig:
            raise cis_profile.exceptions.SignatureVerificationFailure('Signature data in jws does not match '
                                                                      'attribute data => {} != {}'.format(attrnosig,
                                                                                                          signed))

    def sign_all(self, publisher_name):
        """
        Sign all child nodes with a non-null value(s) OR empty values (strict=False)
        To sign empty values, manually call sign_attribute()
        This requires cis_crypto to be properly setup (i.e. with keys)

        WARNING: Since it signs all attributes, this is to be used only when CREATING a new profile. Signing all fields
        while UPDATING a profile is a sure way to cause a validation failure (since no publisher is allowed to modify
        all fields)

        @publisher_name str a publisher name (will be set in signature.publisher.name at signing time)
        """

        logger.debug('Signing all profile fields that have a value set with publisher {}'.format(publisher_name))
        for item in self.__dict__:
            if type(self.__dict__[item]) is not DotDict:
                continue
            try:
                attr = self.__dict__[item]
                if self._attribute_value_set(attr, strict=False):
                    attr = self._sign_attribute(attr, publisher_name)
            except KeyError:
                # This is the 2nd level attribute match, see also initialize_timestamps()
                for subitem in self.__dict__[item]:
                    attr = self.__dict__[item][subitem]
                    if self._attribute_value_set(attr, strict=False):
                        attr = self._sign_attribute(attr, publisher_name)

    def sign_attribute(self, req_attr, publisher_name):
        """
        Sign a single attribute, including null/empty/unset attributes
        @req_attr str this user's attribute to sign in place
        @publisher_name str a publisher name (will be set in signature.publisher.name) which corresponds to the
        signing key
        """
        req_attrs = req_attr.split('.')  # Support subitems/subattributes such as 'access_information.ldap'
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
        if 'value' in attr:
            if attr['value'] is None:
                return False
            elif isinstance(attr['value'], bool):
                return True
            elif not strict and len(attr['value']) == 0:
                return False
        elif 'values' in attr:
            if attr['values'] is None:
                return False
            elif not strict and len(attr['values']) == 0:
                return False
        else:
            raise KeyError(attr)
        return True

    def _sign_attribute(self, attr, publisher_name):
        """
        Perform the actual signature operation
        See also https://github.com/mozilla-iam/cis/blob/profilev2/docs/Profiles.md
        @attr: a CIS Profilev2 attribute
        @publisher_name str a publisher name (will be set in signature.publisher.name) which corresponds to the
        signing key
        """
        # Extract the attribute without the signature structure itself
        attrnosig = attr.copy()
        del attrnosig['signature']
        self.__signop.load(attrnosig)

        # Add the signed attribute back to the original complete attribute structure (with the signature struct)
        # This ensure we also don't touch any existing non-publisher signatures
        sigattr = attr['signature']['publisher']
        sigattr['name'] = publisher_name
        sigattr['alg'] = 'RS256'  # Currently hardcoded in cis_crypto
        sigattr['typ'] = 'JWS'    # ""
        sigattr['value'] = self.__signop.jws()
        return attr
