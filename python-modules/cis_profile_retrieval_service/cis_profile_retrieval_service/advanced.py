"""Support advanced search queries for inclusion in routes via DynamoDb."""
import orjson
import logging
from flask_restful import Resource
from flask_restful import reqparse


from cis_profile import User
from cis_profile_retrieval_service.common import DisplayLevelParms
from cis_profile_retrieval_service.common import scope_to_mozilla_data_classification
from cis_profile_retrieval_service.common import scope_to_display_level
from cis_profile_retrieval_service.idp import requires_auth
from cis_profile_retrieval_service.idp import get_scopes
from cis_identity_vault.models import user
from cis_profile_retrieval_service.common import get_config
from cis_profile_retrieval_service.common import get_dynamodb_client
from cis_profile_retrieval_service.common import get_table_resource
from cis_profile_retrieval_service.exceptions import AuthError


logger = logging.getLogger(__name__)


config = get_config()
dynamodb_table = get_table_resource()
dynamodb_client = get_dynamodb_client()
transactions = config("transactions", namespace="cis", default="false")


allowed_advanced_queries = {
    "access_information.ldap": str,
    "access_information.mozilliansorg": str,
    "staff_information.cost_center": str,
    "staff_information.director": bool,
    "staff_information.manager": bool,
    "staff_information.office_location": str,
    "staff_information.staff": bool,
    "staff_information.team": str,
    "staff_information.title": str,
    "staff_information.worker_type": str,
}


def get_identity_vault():
    if transactions == "false":
        identity_vault = user.Profile(dynamodb_table, dynamodb_client, transactions=False)
    elif transactions == "true":
        identity_vault = user.Profile(dynamodb_table, dynamodb_client, transactions=True)
    else:
        identity_vault = user.Profile(dynamodb_table, dynamodb_client, transactions=False)
    return identity_vault


def filter_full_profiles(scopes, filter_display, vault_profiles):
    v2_profiles = []
    for profile in vault_profiles:
        if isinstance(profile.get("profile"), str):
            vault_profile = orjson.loads(profile.get("profile"))
        else:
            vault_profile = profile.get("profile")

        v2_profile = User(user_structure_json=vault_profile)

        if "read:fullprofile" in scopes:
            # Assume someone has asked for all the data.
            logger.debug(
                "The provided token has access to all of the data.", extra={"scopes": scopes}
            )
            pass
        else:
            # Assume the we are filtering falls back to public with no scopes
            logger.debug("This is a limited scoped query.", extra={"scopes": scopes})
            v2_profile.filter_scopes(scope_to_mozilla_data_classification(scopes))

        if "display:all" in scopes:
            logger.debug("display:all in token not filtering profile.", extra={"scopes": scopes})
        else:
            logger.debug("display filtering engaged for query.", extra={"scopes": scopes})
            v2_profile.filter_display(scope_to_display_level(scopes))

        if filter_display is not None:
            v2_profile.filter_display(DisplayLevelParms.map(filter_display))

        v2_profiles.append(
            dict(
                id=v2_profile.user_id,
                profile=v2_profile.as_dict()
            )
        )

    return v2_profiles


class v2UsersByAttrContains(Resource):

    decorators = [requires_auth]

    def get(self):
        parser = reqparse.RequestParser(bundle_errors=True)
        parser.add_argument("Authorization", location="headers")
        parser.add_argument("filterDisplay", type=str, location="args")

        for attr in allowed_advanced_queries:
            # Ensure that only our allowed attributes are parsed.
            parser.add_argument(attr, type=allowed_advanced_queries[attr], location="args")

        for attr in allowed_advanced_queries:
            # Ensure that only our allowed attributes as inverse ops are parsed.
            parser.add_argument(f"not_{attr}", type=allowed_advanced_queries[attr], location="args")

        parser.add_argument("active", type=bool, location="args")
        parser.add_argument("fullProfiles", type=bool, location="args")
        parser.add_argument("nextPage", type=str, location="args")

        # determine which arg was passed in from the whitelist and then set it up
        reserved_keys = ["active", "nextPage", "fullProfiles", "Authorization", "filterDisplay"]
        args = parser.parse_args()
        scopes = get_scopes(args.get("Authorization"))

        if "search:all" not in scopes:
            raise AuthError(
                {"code": "scope_missing", "description": "This endpoint may only be queried using search:all"}, 401
            )

        for k in args:
            if k not in reserved_keys:
                logger.debug(k)
                attr = k
                if args[attr] is not None:
                    logger.debug(attr)
                    comparator = args[attr]
                    break
        identity_vault = get_identity_vault()
        result = identity_vault.find_by_any(
            attr, comparator, args.get("nextPage", None), args.get("fullProfiles", False), args.get("active", True)
        )

        if args.get("fullProfiles", False):
            filter_display = args.get("filterDisplay", None)
            result["users"] = filter_full_profiles(scopes, filter_display, result["users"])
        return result
