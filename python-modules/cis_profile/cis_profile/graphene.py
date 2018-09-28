"""
Graphene objects that represent the User Profile Schema in Graphene-compatible format.
These can be loaded by libraries or code understanding `graphene.ObjectType`
Object have to be loaded into a `graphene.Schema(graphene.Query(OurTopLevelObject))` style call
"""
import graphene

class UserProfileObjectType(object):
    def __init__(self, classification='PUBLIC'):
        pass

    def initialize(self):
        pass


class UserProfileCoreObjectType(UserProfileObjectType):
    pass

class UserProfileExtendedObjectType(UserProfileObjectType):
    pass
