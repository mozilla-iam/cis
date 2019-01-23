import json
import graphene
import cis_profile.graphene
from cis_identity_vault.models import user
from cis_profile_retrieval_service.common import get_table_resource


def is_json(payload):
    """Check if a payload is valid JSON."""
    try:
        json.loads(payload)
    except (TypeError, ValueError):
        return False
    else:
        return True


class Query(graphene.ObjectType):
    """GraphQL Query class for the V2 Profiles."""

    profiles = graphene.List(cis_profile.graphene.Profile, primaryEmail=graphene.String(required=False))
    profile = graphene.Field(cis_profile.graphene.Profile, userId=graphene.String(required=True))

    def resolve_profiles(self, info, **kwargs):
        """GraphQL resolver for the profiles attribute."""
        table = get_table_resource()
        vault = user.Profile(table)
        profiles = []
        if kwargs.get("primaryEmail"):
            search = vault.find_by_email(kwargs.get("primaryEmail"))
            if len(search.get("Items")) > 0:
                for profile in search.get("Items"):
                    profiles.append(json.loads())
        else:
            for vault_profile in vault.all:
                profiles.append(json.loads(vault_profile.get("profile")))

    def resolve_profile(self, info, **kwargs):
        """GraphQL resolver for a single profile."""
        table = get_table_resource()
        vault = user.Profile(table)

        if kwargs.get("userId"):
            search = vault.find_by_id(kwargs.get("userId"))
            if len(search.get("Items")) > 0:
                resp = search["Items"][0]["profile"]
        else:
            resp = json.dumps({})
        return resp


class AuthorizationMiddleware:
    def resolve(self, next, root, info, **kwargs):
        return next(root, info, **kwargs)
