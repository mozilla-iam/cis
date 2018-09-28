"""
Graphene objects that represent the User Profile Schema in Graphene-compatible format.
These can be loaded by libraries or code understanding `graphene.ObjectType`
Object have to be loaded into a `graphene.Schema(graphene.Query(OurTopLevelObject))` style call
"""
import graphene


class MozillaDataClassification(object):
    """
    See https://wiki.mozilla.org/Security/Data_Classification
    Just a simple object-enum - it returns all valid labels per level
    as a list/array.
    """
    def __init__(self):
        pass

    def _toupper(self, items):
        return [x.upper() for x in items]

    def _tolower(self, items):
        return [x.lower() for x in items]

    def unknown(self):
        r = [ 'UNKNOWN', '', None ]
        return self.toupper(r)+self.tolower(r)

    def public(self):
        r = [ 'PUBLIC' ]
        return self.toupper(r)+self.tolower(r)

    def mozilla_confidential(self):
        r = [ 'Mozilla Confidential - Staff and NDA\'d Mozillians Only', 'MOZILLA CONFIDENTIAL' ]
        return self.toupper(r)+self.tolower(r)

    def workgroup_confidential(self):
        r = [ 'Mozilla Confidential - Specific Work Groups Only', 'WORKGROUP CONFIDENTIAL' ]
        return self.toupper(r)+self.tolower(r)

    def individual_confidential(self):
        r = [ 'Mozilla Confidential - Specific Individuals Only', 'INDIVIDUAL CONFIDENTIAL' ]
        return self.toupper(r)+self.tolower(r)

    def well_known_workgroups(self):
        """
        This is for self.workgroup_confidential() groups that are published by Mozilla
        """
        return [ 'STAFF ONLY' ]

class UserProfileObjectType(object):
    def __init__(self, classification='PUBLIC'):
        pass

    def initialize(self):
        pass


class UserProfileCoreObjectType(UserProfileObjectType):
    pass

class UserProfileExtendedObjectType(UserProfileObjectType):
    pass
