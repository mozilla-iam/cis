#!/usr/bin/env python

import cis_crypto.operation
import json
import json.decoder
try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError
import jsonschema
import logging
import os
import requests
import requests.exceptions
import time

logger = logging.getLogger(__name__)


class DotDict(dict):
    """
    Convert a dict to a fake class/object with attributes, such as:
    test = dict({"test": {"value": 1}})
    test.test.value = 2
    """
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        try:
            # Python2
            for k, v in self.iteritems():
                self.__setitem__(k, v)
        except AttributeError:
            # Python3
            for k, v in self.items():
                self.__setitem__(k, v)

    def __getattr__(self, k):
        try:
            return dict.__getitem__(self, k)
        except KeyError:
            raise AttributeError("'DotDict' object has no attribute '" + str(k) + "'")

    def __setitem__(self, k, v):
        dict.__setitem__(self, k, DotDict.__convert(v))

    __setattr__ = __setitem__

    def __delattr__(self, k):
        try:
            dict.__delitem__(self, k)
        except KeyError:
            raise AttributeError("'DotDict'  object has no attribute '" + str(k) + "'")

    @staticmethod
    def __convert(o):
        """
        Recursively convert `dict` objects in `dict`, `list`, `set`, and
        `tuple` objects to `DotDict` objects.
        """
        if isinstance(o, dict):
            o = DotDict(o)
        elif isinstance(o, list):
            o = list(DotDict.__convert(v) for v in o)
        elif isinstance(o, set):
            o = set(DotDict.__convert(v) for v in o)
        elif isinstance(o, tuple):
            o = tuple(DotDict.__convert(v) for v in o)
        return o


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
                 discovery_url='https://auth.mozilla.com/.well-known/mozilla-iam', schema=None, **kwargs):
        """
        @user_structure_json an existing user structure to load in this class
        @user_structure_json_file an existing user structure to load in this class, from a JSON file
        @discovery_url the well-known Mozilla IAM URL
        @kwargs any user profile attribute name to override on initializing, eg "user_id='test'"
        """
        if schema is None:
            self.__schema = self._load_schema(discovery_url)
        else:
            self.__schema = schema

        if (user_structure_json is not None):
            self.load(user_structure_json)
        elif (user_structure_json_file is not None):
            self.load(self.get_profile_from_file(user_structure_json_file))
        else:
            # Load defaults, including default timestamps
            self.load(self.get_profile_from_file('user_profile_core_plus_extended_null.json'))
            self.initialize_timestamps()

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

    def get_schema(self):
        """
        Public method to grab the schema. This is useful for external caching of the schema.
        (E.g. in case this object is destroyed but cache is to be retained
        """
        if '__schema' in self.__dict__:
            return self.__schema
        else:
            return None

    def _load_schema(self, discovery_url):
        """
        Attempts to fetch latest validation schema, fall-back to cached version on failure.
        See also https://github.com/mozilla-iam/cis/blob/profilev2/docs/.well-known/mozilla-iam.json
        """

        # Check cache first
        if self.get_schema() is not None:
            return self.get_schema()

        schema = None
        schema_url = None

        # Get schema url
        try:
            r = requests.get(discovery_url)
            schema_url = r.json().get('api').get('profile_schema_combined_uri')
        except (JSONDecodeError, requests.exceptions.ConnectionError) as e:
            logger.debug('Failed to fetch schema_url from discovery {} ({})'.format(discovery_url, e))

        # Get schema
        if schema_url is not None:
            try:
                r = requests.get(schema_url)
                schema = r.json()
            except (JSONDecodeError, requests.exceptions.ConnectionError) as e:
                logger.debug('Failed to load schema from schema_url {} ({})'.format(schema_url, e))

        # That did not work, fall-back to local copy
        if schema is None:
            schema_file = "profile.schema"
            if not os.path.isfile(schema_file):
                dirname = os.path.dirname(os.path.realpath(__file__))
                path = dirname + '/' + schema_file
            else:
                path = schema_file

            schema = json.load(open(path))
        return schema

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
            if k.startswith('_{}'.format(classname)):
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

    def validate(self):
        """
        Validates against a JSON schema
        """

        return jsonschema.validate(self.as_dict(), self.__schema)

    def sign_all(self):
        """
        Sign all child nodes with a non-null or non-empty value(s)
        This requires cis_crypto to be properly setup (i.e. with keys)
        """

        logger.debug('Signing all profile fields that have a value set')
        for item in self.__dict__:
            if type(self.__dict__[item]) is not DotDict:
                continue
            try:
                attr = self.__dict__[item]
                if self._attribute_value_set(attr):
                    attr = self._sign_attribute(attr)
            except KeyError:
                # This is the 2nd level attribute match, see also initialize_timestamps()
                for subitem in self.__dict__[item]:
                    attr = self.__dict__[item][subitem]
                    if self._attribute_value_set(attr):
                        attr = self._sign_attribute(attr)

    def sign_attribute(self, req_attr):
        """
        Sign a single attribute, including null/empty/unset attributes
        """
        req_attrs = req_attr.split('.')  # Support subitems/subattributes such as 'access_information.ldap'
        if len(req_attrs) == 1:
            attr = self.__dict__[req_attr]
        else:
            attr = self.__dict__[req_attrs[0]][req_attrs[1]]
        return self._sign_attribute(attr)

    def _attribute_value_set(self, attr):
        """
        Checks if an attribute is used/set, ie not null or empty
        @attr a complete CIS Profilev2 attribute (such as {'test': {'value': null}})
        returns: True if the attribute has a value, False if not
        """
        if 'value' in attr:
            if attr['value'] is None:
                return False
            elif isinstance(attr['value'], bool):
                return True
            elif len(attr['value']) == 0:
                return False
        elif 'values' in attr:
            if attr['values'] is None:
                return False
            elif len(attr['values']) == 0:
                return False
        else:
            raise KeyError(attr)
        return True

    def _sign_attribute(self, attr):
        """
        Perform the actual signature operation
        See also https://github.com/mozilla-iam/cis/blob/profilev2/docs/Profiles.md
        @attr: a CIS Profilev2 attribute
        """
        # Extract the attribute without the signature structure itself
        attrnosig = attr.copy()
        del attrnosig['signature']
        self.__signop.load(attrnosig)

        # Add the signed attribute back to the original complete attribute structure (with the signature struct)
        # This ensure we also don't touch any existing non-publisher signatures
        sigattr = attr['signature']['publisher']
        sigattr['alg'] = 'RS256'  # Currently hardcoded in cis_crypto
        sigattr['typ'] = 'JWS'    # ""
        sigattr['value'] = self.__signop.jws()
        return attr
