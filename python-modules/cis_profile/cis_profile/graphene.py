"""
Graphene objects that represent the User Profile Schema in Graphene-compatible format.
These can be loaded by libraries or code understanding `graphene.ObjectType`
Object have to be loaded into a `graphene.Schema(graphene.Query(OurTopLevelObject))` style call
"""
import datetime
import graphene
import json

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
    Graphene Scalar for our date time format
    """

    @staticmethod
    def serialize(dt):
        return dt.isoformat()

    @staticmethod
    def parse_literal(node):
        if isinstance(node, ast.StringValue):
            return datetime.datetime.strptime(node.value, "%Y-%m-%dT%H:%M:%S.%f")

    @staticmethod
    def parse_value(value):
        return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f")


class GDict(Scalar):
    """
    Graphene Scalar for dictionaries
    """

    @staticmethod
    def serialize(gdict):
        return gdict

    @staticmethod
    def parse_literal(node):
        if isinstance(node, ast.ObjectValue):
            return node

    @staticmethod
    def parse_value(value):
        return json.loads(value)


# Profile enums
class Alg(graphene.Enum):
    """
    Supported signature algorithms
    """

    HS256 = "HS256"
    RS256 = "RS256"
    RSA = "RSA"
    ED25519 = "ED25519"


class Typ(graphene.Enum):
    """
    Supported signature types
    """

    JWT = "JWT"
    PGP = "PGP"


class Classification(graphene.Enum):
    """
    Mozilla data classification
    """

    MOZILLA_CONFIDENTIAL = "MOZILLA CONFIDENTIAL"
    PUBLIC = "PUBLIC"
    WORKGROUP_CONFIDENTIAL = "WORKGROUP CONFIDENTIAL"
    STAFF_ONLY = "WORKGROUP CONFIDENTIAL: STAFF ONLY"
    INDIVIDUAL_CONFIDENTIAL = "INDIVIDUAL CONFIDENTIAL"


# Standard properties
class Display(graphene.Enum):
    """
    DinoPark visibility/display intent
    """

    public = "public"
    authenticated = "authenticated"
    vouched = "vouched"
    ndaed = "ndaed"
    staff = "staff"
    private = "private"
    null = "null"


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


class StandardAttributeBoolean(StandardProperty):
    value = graphene.Boolean()


class StandardAttributeDateTime(StandardProperty):
    value = DateTime()


class StandardAttributeDict(StandardProperty):
    """
    graphene requires Fields (dicts) to have well-known keys
    we define a custom dict scalar to solve for this.
    """

    values = GDict()

    def resolve_values(self, *args, **kwargs):
        return self["values"]


# Profile advanced properties
class AccessInformation(StandardProperty):
    ldap = graphene.Field(StandardAttributeDict)
    mozilliansorg = graphene.Field(StandardAttributeDict)
    hris = graphene.Field(StandardAttributeDict)
    access_provider = graphene.Field(StandardAttributeDict)


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
    mozilliansorg_id = graphene.Field(StandardAttributeString)
    bugzilla_mozilla_org_id = graphene.Field(StandardAttributeString)
    mozilla_ldap_id = graphene.Field(StandardAttributeString)
    mozilla_posix_id = graphene.Field(StandardAttributeString)
    google_oauth2_id = graphene.Field(StandardAttributeString)
    firefox_accounts_id = graphene.Field(StandardAttributeString)
    custom_1_primary_email = graphene.Field(StandardAttributeString)
    custom_2_primary_email = graphene.Field(StandardAttributeString)
    custom_3_primary_email = graphene.Field(StandardAttributeString)


## Profiles
class Profile(graphene.ObjectType):
    """
    IAM Profile v2
    """

    user_id = graphene.Field(StandardAttributeString)
    uuid = graphene.Field(StandardAttributeString)
    username = graphene.Field(StandardAttributeString)
    login_method = graphene.Field(StandardAttributeString)
    active = graphene.Field(StandardAttributeBoolean)
    last_modified = graphene.Field(StandardAttributeDateTime)
    created = graphene.Field(StandardAttributeDateTime)
    usernames = graphene.Field(StandardAttributeDict)
    first_name = graphene.Field(StandardAttributeString)
    last_name = graphene.Field(StandardAttributeString)
    primary_email = graphene.Field(StandardAttributeString)
    identities = graphene.Field(Identities)
    ssh_public_keys = graphene.Field(StandardAttributeDict)
    pgp_public_keys = graphene.Field(StandardAttributeDict)
    access_information = graphene.Field(AccessInformation)
    fun_title = graphene.Field(StandardAttributeString)
    description = graphene.Field(StandardAttributeString)
    location = graphene.Field(StandardAttributeString)
    timezone = graphene.Field(StandardAttributeString)
    language = graphene.Field(StandardAttributeString)
    tags = graphene.Field(StandardAttributeDict)
    pronouns = graphene.Field(StandardAttributeString)
    picture = graphene.Field(StandardAttributeString)
    uris = graphene.Field(StandardAttributeDict)
    phone_numbers = graphene.Field(StandardAttributeDict)
    alternative_name = graphene.Field(StandardAttributeString)
    staff_information = graphene.Field(StaffInformation)
