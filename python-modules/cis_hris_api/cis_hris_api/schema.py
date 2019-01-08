import json
import graphene
from logging import getLogger
from cis_hris_api.common import get_table_resource
from cis_hris_api import user

logger = getLogger(__name__)


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


class HRISAttributes(graphene.ObjectType):
    """V2 Schema HRIS object for Graphene.
    This is a well-known lists of HRIS attributes.
    """
    preferred_first_name = graphene.String()
    preferred_last_name = graphene.String()
    preferred_name = graphene.String()
    location_description = graphene.String()
    team = graphene.String()
    wpr_desk_number = graphene.String()
    worker_type = graphene.String()
    manager_email = graphene.String()
    business_title = graphene.String()
    is_director_or_above = graphene.String()
    primary_email = graphene.String()
    employee_id = graphene.String()


class Query(graphene.ObjectType):
    """GraphQL Query class for the V2 Profiles."""
    profiles = graphene.List(HRISAttributes)
    profile = graphene.Field(
        HRISAttributes,
        primary_email=graphene.String(required=True)
    )

    def resolve_profiles(self, info, **kwargs):
        """GraphQL resolver for the profiles attribute."""
        table = get_table_resource()
        vault = user.Profile(table)
        logger.info('Returning all profiles from the vault.')
        profiles = []
        for profile in vault.all:
            resolved_fields = {
                f: profile[f] for f in HRISAttributes._meta.fields
            }

            profiles.append(HRISAttributes(**resolved_fields))
        return profiles

    def resolve_profile(self, info, **kwargs):
        """GraphQL resolver for a single profile."""
        table = get_table_resource()
        vault = user.Profile(table)

        if kwargs.get('primary_email'):
            search = vault.find_by_email(kwargs.get('primary_email'))
            if len(search.get('Items')) > 0:
                logger.info('Profile found for query: {}'.format(kwargs))
                resp = search['Items'][0]
                resolved_fields = {
                    f: resp[f] for f in HRISAttributes._meta.fields
                }
        else:
            resp = {}
        return HRISAttributes(**resolved_fields)


class AuthorizationMiddleware():
    def resolve(self, next, root, info, **kwargs):
        return next(root, info, **kwargs)
