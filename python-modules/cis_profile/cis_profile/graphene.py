"""
Graphene objects that represent the User Profile Schema in Graphene-compatible format.
These can be loaded by libraries or code understanding `graphene.ObjectType`
Object have to be loaded into a `graphene.Schema(graphene.Query(OurTopLevelObject))` style call
"""
from cis_profile.common import WellKnown
from cis_profile.common import DotDict

import graphene

class UserProfileObjectType(object):
    def __init__(self, classification='PUBLIC'):
        # Semi-passive, no-fail functions
        self._well_known_json = WellKnown()
        self._schema = self._well_known_json.get_schema()

    def load(self):
        """
        Schema format summary:
        JSON: 
          $schema: ...
          $ref: ...
          definitions: 
            ...
            Metadata:
              type: object
              additionalProperties: false
              properties:
                classification:
                    $ref: #/definitions/Classification
                created:
                    type: string
                    format: date-time
                last_modified:
                    type: string
                    format: date-time
                verified:
                    type: boolean
                ...
                Name:
                Value:
              required:
                0: classification
                1: created
                2: last_modified
                3: verified
              title: Metadata
            Classification:
            ...
        ...
        """
        if (self._schema.get('$ref') != '#/definitions/CorePlusExtendedProfile'):
            raise('SchemaLoadingError', 'Invalid schema reference')

        definitions = DotDict(self._schema.get('definitions'))
        for definition_name in definitions:
            # graphene has either basic objects which are type primitives (bool, str, int, ...)
            # and custom objects which are basically object, dict, etc (i.e. structures of structures and/or of type
            # primitives) so we detect that
            current_def = definitions[definition_name]
            print(definition_name)
            if current_def.type != 'object':
                pass

class UserProfileCoreObjectType(UserProfileObjectType):
    pass

class UserProfileExtendedObjectType(UserProfileObjectType):
    pass
