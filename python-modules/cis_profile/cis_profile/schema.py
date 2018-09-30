import json
import logging


logger = logging.getLogger(__name__)


class SchemaPropertyDefinition(dict):
    """
    A JSON Schema property definition which is the base object used by all JSON Schemas.
    @typ str object type (object, str, bool, int, ...)
    @title str a title for the definition
    @enum list optional list of allowed values
    @additionalProperties bool true if unspecified properties are allowed
    @required list optional list of required values
    @properties dict if this is an object definition, define the sub-properties here
    """
    def __init__(self, typ='string', title='', enum=None, additionalProperties=False, required=None, properties=None):
        # Bare defaults
        self._property_def = {'type': typ, 'title': title, 'additionalProperties': additionalProperties}

        # Basic error checking
        if typ == 'object' and properties is None:
            raise KeyError('You must have properties in an object')

        if properties is not None and enum is not None:
            raise KeyError('You cannot have an enum and properties in the same object')

        if typ not in ['object', 'string', 'boolean', 'integer']:
            raise KeyError('Invalid or unsupported type (typ)')

        # Fill in the rest
        if enum is not None:
            self._property_def['enum'] = enum

        if required is not None:
            self._property_def['required'] = required

        if properties is not None:
            self._property_def['properties'] = properties

        # Make-me-a-dict
        self.update(self._property_def)


class UserProfileSchema(object):
    def __init__(self):
        """
        This is where the user profile schema is defined
        These values drive how the schema works.
        """
        # Internal version reference of when this class was last modified
        self.version = '2018-09-30'

        # ALL schema property definitions must be listed here
        self.definitions = ['Profile',                             # Main profile data
                            'Metadata',                            # Metadata for attributes
                            'Classification',                      # Metadata.Classification
                            'Signature',                           # Signature for attributes
                            'Alg',                                 # Signature.Alg
                            'Typ',                                 # Signature.Typ
                            'Publisher',                           # Signature.Publisher
                            'PublisherLax',                        # Same but relaxed checks for attr creation
                            'PublisherAuthority',                  # List of all known publishers
                            'AccessInformation',                   # "Groups"
                            'AccessInformationProviderSubObject',  # AccessInformation.AccessInformationProviderSub..
                            'AccessInformationValues',             # AccessInformation....Sub...AccessInformationValues
                            'Identities',                          # List of user identities
                            'IdentitiesValues',                    # Identities.IdentitiesValues
                            'StandardAttributeBoolean',            # Generic type for bool
                            'StandardAttributeValues',             # " for Values array-or-object
                            'StandardAttributeString']             # " for str

        p = dict()
        profile_properties = ['schema',                 # The schema URI
                              'user_id',                # UUID for the user
                              'active',                 # If the user is allowed to login or not
                              'created',                # Creation date
                              'last_modified',          # Last profile modification date
                              'first_name',             # Preferred first name
                              'last_name',              # Preferred last name
                              'login_method',           # Preferred login method (GitHub, Google, etc.)
                              'primary_email',          # Primary email for this profile
                              'identities',             # List of associated identities or accounts
                              'usernames',              # List of known user names - similar to identities but lighter
                              'ssh_public_keys',        # List of known SSH public keys
                              'pgp_public_keys',        # List of known PGP public keys
                              'access_information']     # List of assertions about the user used for access control

        p['Profile'] = SchemaPropertyDefinition(title='Profile', typ='object', required=profile_properties,
                                                properties=profile_properties)


        # Create the schema
        self.init_base_schema()
        self.init_definitions()
        self.init_properties()

    def init_base_schema(self, ref='#/definitions/CorePlusExtendedProfile'):
        # Base schema
        self._schema = {'$schema': 'http://json-schema.org/draft-04/schema#',
                         '$ref': ref,
                         'definitions': {}}

    def init_definitions(self):
        for d in self.definitions:
            self._schema[d] = SchemaPropertyDefinition(title=d)

    def init_properties(self):
        pass

    def as_json(self):
        return json.dumps(self._schema)



