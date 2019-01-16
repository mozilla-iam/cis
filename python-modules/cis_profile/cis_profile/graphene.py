"""
Graphene objects that represent the User Profile Schema in Graphene-compatible format.
These can be loaded by libraries or code understanding `graphene.ObjectType`
Object have to be loaded into a `graphene.Schema(graphene.Query(OurTopLevelObject))` style call
"""
import datetime
import graphene

from graphene.types import Scalar
from graphql.language import ast


# XXX use a schema generator for all things schema instead of this as other classes use the schema file as input
# while this part of the code hardcodes the schema. Generating classes or classes seems to be a little hard to
# read or understand for mere mortals, eg:
# class list: self.classes.append(type("classname", (object), {'val': 'test', 'func': func})
# This causes issues particularly if you need to draw a tree of interdependent classes (ie `func` above is part of a
# class that is not-yet-generated, thus a tree of dependencies is first resolved, then class lists generated, which
# seems frankly overkill
# See commit c38f00975896cb60a1467e3315d2291dd5f31657 for a Schema generator head-start

# Required non-scalar to scalar transforms
class DateTime(Scalar):
    """
    Graphene Scaler for our date time format
    """
    @staticmethod
    def serialize(dt):
        return dt.isoformat()

    @staticmethod
    def parse_literal(node):
        if isinstance(node, ast.StringValue):
            return datetime.datetime.strptime(
                node.value, "%Y-%m-%dT%H:%M:%S.%f")

    @staticmethod
    def parse_value(value):
        return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f")


# Profile enums
class Alg(graphene.Enum):
    """
    Supported signature algorithms
    """
    HS256 = 'HS256'
    RS256 = 'RS256'
    RSA = 'RSA'
    ED25519 = 'ED25519'


class Typ(graphene.Enum):
    """
    Supported signature types
    """
    JWT = 'JWT'
    PGP = 'PGP'


class Classification(graphene.Enum):
    """
    Mozilla data classification
    """
    MOZILLA_CONFIDENTIAL = 'MOZILLA CONFIDENTIAL'
    PUBLIC = 'PUBLIC'
    WORKGROUP_CONFIDENTIAL = 'WORKGROUP CONFIDENTIAL'
    STAFF_ONLY = 'WORKGROUP CONFIDENTIAL: STAFF ONLY'
    INDIVIDUAL_CONFIDENTIAL = 'INDIVIDUAL CONFIDENTIAL'


# Standard properties
class Display(graphene.Enum):
    """
    DinoPark visibility/display intent
    """
    public = 'public'
    authenticated = 'authenticated'
    vouched = 'vouched'
    ndaed = 'ndaed'
    staff = 'staff'
    private = 'private'
    null = 'null'


class Metadata(graphene.ObjectType):
    classification = graphene.Field(Classification)
    last_modified = DateTime()
    created = DateTime()
    verified = graphene.Boolean()
    display = graphene.Field(Display)


class SignatureField(graphene.ObjectType):
    alg = graphene.Field(Alg)
    typ = graphene.Field(Typ)
    name = graphene.String()
    value = graphene.String()


class Signature(graphene.ObjectType):
    publisher = graphene.Field(SignatureField)
    additional = graphene.List(SignatureField)


class StandardProperty(graphene.ObjectType):
    signature = graphene.Field(Signature)
    metadata = graphene.Field(Metadata)


class StandardAttributeString(StandardProperty):
    value = graphene.String()


class StandardAttributeList(StandardProperty):
    values = graphene.List(graphene.String)


class StandardAttributeBoolean(StandardProperty):
    value = graphene.Boolean()


class StandardAttributeDateTime(StandardProperty):
    value = DateTime()


class StandardAttributeFieldList(StandardProperty):
    """
    graphene requires Fields (dicts) to have well-known keys
    work-around this by providing a list of fields through a graphene List
    """
    values = graphene.List(graphene.String)

    def resolve_values(self, info, *kwargs):
        values = self.get('values')
        if values:
            return values.items()
        else:
            return None


# Profile advanced properties
class AccessInformation(StandardProperty):
    ldap = graphene.Field(StandardAttributeFieldList)
    mozilliansorg = graphene.Field(StandardAttributeFieldList)
    hris = graphene.Field(StandardAttributeFieldList)
    access_provider = graphene.Field(StandardAttributeFieldList)


# Profiles
class StaffInformation(StandardProperty):
    manager = graphene.Field(StandardAttributeString)
    director = graphene.Field(StandardAttributeString)
    staff = graphene.Field(StandardAttributeString)
    title = graphene.Field(StandardAttributeString)
    team = graphene.Field(StandardAttributeString)
    cost_center = graphene.Field(StandardAttributeString)
    worker_type = graphene.Field(StandardAttributeString)
    wpr_desk_number = graphene.Field(StandardAttributeString)
    office_location = graphene.Field(StandardAttributeString)


class Identities(StandardProperty):
    github_id_v3 = graphene.Field(StandardAttributeString)
    github_id_v4 = graphene.Field(StandardAttributeString)
    dinopark_id = graphene.Field(StandardAttributeString)
    mozilliansorg_id = graphene.Field(StandardAttributeString)
    bugzilla_mozilla_org_id = graphene.Field(StandardAttributeString)
    mozilla_ldap_id = graphene.Field(StandardAttributeString)
    mozilla_posix_id = graphene.Field(StandardAttributeString)
    google_oauth2_id = graphene.Field(StandardAttributeString)
    firefox_accounts_id = graphene.Field(StandardAttributeString)


## Profiles
class Profile(graphene.ObjectType):
    """
    IAM Profile v2
    """
    user_id = graphene.Field(StandardAttributeString)
    login_method = graphene.Field(StandardAttributeString)
    active = graphene.Field(StandardAttributeBoolean)
    last_modified = graphene.Field(StandardAttributeDateTime)
    created = graphene.Field(StandardAttributeDateTime)
    usernames = graphene.Field(StandardAttributeList)
    first_name = graphene.Field(StandardAttributeString)
    last_name = graphene.Field(StandardAttributeString)
    primary_email = graphene.Field(StandardAttributeString)
    identities = graphene.Field(Identities)
    ssh_public_keys = graphene.Field(StandardAttributeFieldList)
    pgp_public_keys = graphene.Field(StandardAttributeFieldList)
    access_information = graphene.Field(AccessInformation)
    fun_title = graphene.Field(StandardAttributeString)
    description = graphene.Field(StandardAttributeString)
    location = graphene.Field(StandardAttributeString)
    timezone = graphene.Field(StandardAttributeString)
    language = graphene.Field(StandardAttributeString)
    tags = graphene.Field(StandardAttributeList)
    pronouns = graphene.Field(StandardAttributeString)
    picture = graphene.Field(StandardAttributeString)
    uris = graphene.Field(StandardAttributeFieldList)
    phone_numbers = graphene.Field(StandardAttributeFieldList)
    alternative_name = graphene.Field(StandardAttributeString)
    staff_information = graphene.Field(StaffInformation)
