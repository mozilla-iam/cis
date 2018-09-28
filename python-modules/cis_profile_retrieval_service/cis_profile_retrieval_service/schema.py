import json
import graphene
import os
import requests
from aniso8601 import parse_datetime

from cis_identity_vault.models import user
from cis_profile_retrieval_service import get_config
from cis_profile_retrieval_service import get_table_resource
from cis_profile_retrieval_service.idp import requires_scope


# Helper functions
def parse_datetime_iso8601(datetime):
    """Parse a string in ISO8601 format."""
    if not datetime:
        return None

    try:
        dt = parse_datetime(datetime)
    except ValueError:
        return None
    else:
        return dt


def is_json(payload):
    """Check if a payload is valid JSON."""
    try:
        json.loads(payload)
    except (TypeError, ValueError):
        return False
    else:
        return True


class ObjectFactory(dict):
    """Allows to parse a dict structure with an object like notation (attributes)."""

    def __init__(self, data={}):
        super(ObjectFactory, self).__init__()
        for k, v in data.items():
            self.__setitem__(k, v)

    def __setitem__(self, key, value):
        if isinstance(value, dict):
            value = ObjectFactory(value)
        super(ObjectFactory, self).__setitem__(key, value)

    def __getattr__(self, item):
        try:
            return self.__getitem__(item)
        except KeyError:
            raise AttributeError(item)

    __setattr__ = __setitem__


def object_hook(dct):
    """Transform every JSON object to Python objects."""
    return ObjectFactory(dct)


def json2obj(data):
    return json.loads(data, object_hook=object_hook)


class Alg(graphene.Enum):
    """V2 Schema Alg object for Graphene."""

    HS256 = 'HS256'
    RS256 = 'RS256'
    RSA = 'RSA'
    ED25519 = 'ED25519'


class Typ(graphene.Enum):
    """V2 Schema Typ object for Graphene."""

    JWT = 'JWT'
    PGP = 'PGP'


class Classification(graphene.Enum):
    """V2 Schema Classification object for Graphene."""

    MOZILLA_CONFIDENTIAL = 'MOZILLA CONFIDENTIAL'
    PUBLIC = 'PUBLIC'
    INDIVIDUAL_CONFIDENTIAL = 'INDIVIDUAL CONFIDENTIAL'
    STAFF_ONLY = 'WORKGROUP CONFIDENTIAL: STAFF ONLY'


class Publisher(graphene.ObjectType):
    """V2 Schema Publisher object for Graphene."""

    alg = graphene.Field(Alg)
    typ = graphene.Field(Typ)
    value = graphene.String()


class Signature(graphene.ObjectType):
    """V2 Schema Signature object for Graphene."""

    publisher = graphene.Field(Publisher)
    additional = graphene.List(Publisher)


class Metadata(graphene.ObjectType):
    """V2 Schema Metadata object for Graphene."""

    classification = graphene.Field(Classification)
    last_modified = graphene.DateTime()
    created = graphene.DateTime()
    verified = graphene.Boolean()

    def resolve_last_modified(self, info, **kwargs):
        """Resolver to return a datetime object."""
        return parse_datetime_iso8601(self.get('last_modified'))

    def resolve_created(self, info, **kwargs):
        """Resolver to return a datetime object."""
        return parse_datetime_iso8601(self.get('created'))


class BaseObjectType(graphene.ObjectType):
    """V2 Schema Base object object for Graphene."""
    signature = graphene.Field(Signature)
    metadata = graphene.Field(Metadata)


class StandardAttributeDatetime(BaseObjectType):
    """V2 Schema StandardAttributeDatetime object for Graphene."""

    value = graphene.DateTime()

    def resolve_value(self, info, **kwargs):
        """Resolver to return a datetime object."""
        return parse_datetime_iso8601(self.get('value'))


class StandardAttributeBoolean(BaseObjectType):
    """V2 Schema StandardAttributeBoolean object for Graphene."""

    value = graphene.Boolean()


class StandardAttributeString(BaseObjectType):
    """V2 Schema StandardAttributeString object for Graphene."""

    value = graphene.String()


class IdentitiesValues(graphene.ObjectType):
    """V2 Schema IdentitiesValues object for Graphene."""

    github_id_v3 = graphene.String()
    github_id_v4 = graphene.String()
    LDAP = graphene.String()
    bugzilla = graphene.String()
    google = graphene.String()
    firefoxaccounts = graphene.String()
    emails = graphene.List(graphene.String)

    def resolve_bugzilla(self, info, **kwargs):
        """Custom resolver for the Bugzilla Identity.

        Extract the bugzilla.mozilla.org Identity from the profile v2 schema.
        """
        return self.get('bugzilla.mozilla.org')

    def resolve_google(self, info, **kwargs):
        """Custom resolver for the Google Identity.

        Extract the google-oauth2 Identity from the profile v2 schema.
        """
        return self.get('google-oauth2')


class Identities(BaseObjectType):
    """V2 Schema Identities object for Graphene."""

    values = graphene.Field(IdentitiesValues)

    def resolve_values(self, info, **kwargs):
        return self.get('values')


class StandardAttributeValues(BaseObjectType):
    """V2 Schema StandardAttributeValues object for Graphene."""

    values = graphene.List(graphene.String)

    def resolve_values(self, info, **kwargs):
        """Custom resolver for the list of values."""
        if isinstance(self['values'], list):
            return self['values']
        values = self.get('values')
        if values:
            return values.items()
        return None


class PublicEmailAddresses(graphene.ObjectType):
    """HRIS schema for public email addresses."""
    PublicEmailAddress = graphene.String(name='publicEmailAddress')


class HRISAttributes(graphene.ObjectType):
    """V2 Schema HRIS object for Graphene.

    This is a well-known lists of HRIS attributes.
    """
    Last_Name = graphene.String(required=True, name='lastName')
    Preferred_Name = graphene.String(required=True, name='preferredName')
    PreferredFirstName = graphene.String(required=True, name='preferredFirstName')
    LegalFirstName = graphene.String(required=True, name='legalFirstName')
    EmployeeID = graphene.String(required=True, name='employeeId')
    businessTitle = graphene.String(required=True)
    IsManager = graphene.Boolean(required=True, name='isManager')
    isDirectorOrAbove = graphene.Boolean(required=True)
    Management_Level = graphene.String(required=True, name='managementLevel')
    HireDate = graphene.DateTime(required=True, name='hireDate')
    CurrentlyActive = graphene.Boolean(required=True, name='currentlyActive')
    Entity = graphene.String(required=True, name='entity')
    Team = graphene.String(required=True, name='team')
    Cost_Center = graphene.String(required=True, name='costCenter')
    WorkerType = graphene.String(required=True, name='workerType')
    LocationDescription = graphene.String(name='locationDescription')
    Time_Zone = graphene.String(required=True, name='timeZone')
    LocationCity = graphene.String(required=True, name='locationCity')
    LocationState = graphene.String(required=True, name='locationState')
    LocationCountryFull = graphene.String(required=True, name='locationCountryFull')
    LocationCountryISO2 = graphene.String(required=True, name='locationCountryIso2')
    WorkersManager = graphene.String(name='workersManager')
    WorkersManagerEmployeeID = graphene.String(required=True, name='workersManagerEmployeeId')
    Worker_s_Manager_s_Email_Address = graphene.String(required=True,
                                                       name='workersManagersEmailAddress')
    PrimaryWorkEmail = graphene.String(required=True, name='primaryWorkEmail')
    WPRDeskNumber = graphene.String(name='wprDeskNumber')
    EgenciaPOSCountry = graphene.String(required=True, name='egenciaPosCountry')
    PublicEmailAddresses = graphene.List(PublicEmailAddresses, name='publicEmailAddresses')


class HRISAttributeValues(BaseObjectType):
    """V2 Schema StandardAttributeValues object for Graphene."""

    values = graphene.Field(HRISAttributes)

    def resolve_values(self, info, **kwargs):
        return self.get('values')


class AccessInformation(graphene.ObjectType):
    """V2 Schema AccessInformation object for Graphene."""

    ldap = graphene.Field(StandardAttributeValues)
    mozilliansorg = graphene.Field(StandardAttributeValues)
    hris = graphene.Field(HRISAttributeValues)
    access_provider = graphene.Field(StandardAttributeValues)


class CoreProfile(graphene.ObjectType):
    """V2 Schema CoreProfile object for Graphene."""

    user_id = graphene.Field(StandardAttributeString)
    login_method = graphene.Field(StandardAttributeString)
    active = graphene.Field(StandardAttributeBoolean)
    last_modified = graphene.Field(StandardAttributeDatetime)
    created = graphene.Field(StandardAttributeDatetime)
    usernames = graphene.Field(StandardAttributeValues)
    first_name = graphene.Field(StandardAttributeString)
    last_name = graphene.Field(StandardAttributeString)
    primary_email = graphene.Field(StandardAttributeString)
    identities = graphene.Field(Identities)
    ssh_public_keys = graphene.Field(StandardAttributeValues)
    pgp_public_keys = graphene.Field(StandardAttributeValues)
    access_information = graphene.Field(AccessInformation)
    fun_title = graphene.Field(StandardAttributeString)
    description = graphene.Field(StandardAttributeString)
    location_preference = graphene.Field(StandardAttributeString)
    office_location = graphene.Field(StandardAttributeString)
    timezone = graphene.Field(StandardAttributeString)
    preferred_language = graphene.Field(StandardAttributeValues)
    tags = graphene.Field(StandardAttributeValues)
    pronouns = graphene.Field(StandardAttributeString)
    picture = graphene.Field(StandardAttributeString)
    uris = graphene.Field(StandardAttributeValues)
    phone_numbers = graphene.Field(StandardAttributeValues)
    alternative_name = graphene.Field(StandardAttributeString)


class Query(graphene.ObjectType):
    """GraphQL Query class for the V2 Profiles."""
    if scope('blah'):
        profiles = graphene.List(CISProfileSchema(scope), primaryEmail=graphene.String(required=False))
    elif scope('blah blah')
        profiles = graphene.List(SuperCoreProfile, primaryEmail=graphene.String(required=False))

    profile = graphene.Field(CoreProfile, userId=graphene.String(required=True))

    def resolve_profiles(self, info, **kwargs):
        print(info.context.headers)
        """GraphQL resolver for the profiles attribute."""
        table = get_table_resource()
        vault = user.Profile(table)
        profiles = []
        if kwargs.get('primaryEmail'):
            search = vault.find_by_email(kwargs.get('primaryEmail'))
            if len(search.get('Items')) > 0:
                for profile in search.get('Items'):
                    profiles.append(json.loads(profile.get('profile')))
        else:
            for vault_profile in vault.all:
                profiles.append(json.loads(vault_profile.get('profile')))
        return json2obj(json.dumps(profiles))

    def resolve_profile(self, info, **kwargs):
        """GraphQL resolver for a single profile."""
        table = get_table_resource()
        vault = user.Profile(table)

        if kwargs.get('userId'):
            search = vault.find_by_id(kwargs.get('userId'))
            if len(search.get('Items')) > 0:
                resp = search['Items'][0]['profile']
        else:
            resp = json.dumps({})
        return json2obj(resp)

class AuthorizationMiddleware():
    def resolve(self, next, root, info, **kwargs):
        authorization_headers = info.context.headers


        return next(root, info, **kwargs)
