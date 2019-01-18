import json
import re

from flask import Flask
from flask_cors import CORS
from flask_graphql import GraphQLView
from flask_restful import Api
from flask_restful import Resource
from flask_restful import reqparse
from flask import jsonify
from graphene import Schema
from logging import getLogger
import urllib.parse

from cis_identity_vault.models import user
from cis_profile.common import MozillaDataClassification
from cis_profile.common import DisplayLevel
from cis_profile.profile import User
from cis_profile_retrieval_service.common import get_config
from cis_profile_retrieval_service.common import initialize_vault
from cis_profile_retrieval_service.common import get_dynamodb_client
from cis_profile_retrieval_service.common import get_table_resource
from cis_profile_retrieval_service.common import seed
from cis_profile_retrieval_service.schema import Query
from cis_profile_retrieval_service.schema import AuthorizationMiddleware
from cis_profile_retrieval_service.idp import requires_auth
from cis_profile_retrieval_service.idp import get_scopes


app = Flask(__name__)
api = Api(app)
CORS(app)
config = get_config()
logger = getLogger(__name__)

if config("initialize_vault", namespace="person_api", default="false") == "true":
    logger.debug("Initializing vault and pre-seeding it, this will take some time...")
    initialize_vault()
    seed()
    logger.debug("Vault is seeded and ready to go!")

authorization_middleware = AuthorizationMiddleware()
dynamodb_table = get_table_resource()
dynamodb_client = get_dynamodb_client()
transactions = config("transactions", namespace="cis", default="false")


def load_dirty_json(dirty_json):
    regex_replace = [
        (r"([ \{,:\[])(u)?'([^']+)'", r'\1"\3"'),
        (r" False([, \}\]])", r" false\1"),
        (r" True([, \}\]])", r" true\1"),
    ]
    for r, s in regex_replace:
        dirty_json = re.sub(r, s, dirty_json)
    clean_json = json.loads(dirty_json)
    return clean_json


def scope_to_mozilla_data_classification(scopes):
    classifications = []
    if "classification:mozilla_confidential" in scopes:
        logger.debug("Mozilla confidential data classification in scope.")
        classifications.append(MozillaDataClassification.MOZILLA_CONFIDENTIAL)

    if "classification:workgroup:staff_only" in scopes:
        logger.debug("Workgroup: staff only data classification in scope.")
        classifications.append(MozillaDataClassification.STAFF_ONLY)

    if "classification:workgroup" in scopes:
        logger.debug("Workgroup data classification in scope.")
        classifications.append(MozillaDataClassification.WORKGROUP_CONFIDENTIAL)

    if "classification:individual" in scopes:
        logger.debug("Individual data classification in scope.")
        classifications.append(MozillaDataClassification.INDIVIDUAL_CONFIDENTIAL)

    classifications.append(MozillaDataClassification.PUBLIC)
    return classifications


class DisplayLevelParms(object):
    public = [DisplayLevel.PUBLIC]
    authenticated = [DisplayLevel.PUBLIC, DisplayLevel.AUTHENTICATED]
    vouched = [DisplayLevel.PUBLIC, DisplayLevel.AUTHENTICATED, DisplayLevel.VOUCHED]
    ndaed = [DisplayLevel.PUBLIC, DisplayLevel.AUTHENTICATED, DisplayLevel.VOUCHED, DisplayLevel.NDAED]
    staff = [
        DisplayLevel.PUBLIC,
        DisplayLevel.AUTHENTICATED,
        DisplayLevel.VOUCHED,
        DisplayLevel.NDAED,
        DisplayLevel.STAFF,
    ]
    private = [
        DisplayLevel.PUBLIC,
        DisplayLevel.AUTHENTICATED,
        DisplayLevel.VOUCHED,
        DisplayLevel.NDAED,
        DisplayLevel.STAFF,
        DisplayLevel.PRIVATE,
    ]

    @classmethod
    def map(cls, display_level):
        return getattr(cls, display_level, cls.public)


def scope_to_display_level(scopes):
    display_levels = []
    if "display:all" in scopes:
        logger.debug("all display level in scope.")
        display_levels.append(DisplayLevel.NONE)

    if "display:staff" in scopes:
        logger.debug("staff display level in scope.")
        display_levels.append(DisplayLevel.STAFF)

    if "display:ndaed" in scopes:
        logger.debug("ndaed display level in scope.")
        display_levels.append(DisplayLevel.NDAED)

    if "display:vouched" in scopes:
        logger.debug("vouched display level in scope.")
        display_levels.append(DisplayLevel.VOUCHED)

    if "display:authenticated" in scopes:
        logger.debug("authenticated display level in scope.")
        display_levels.append(DisplayLevel.AUTHENTICATED)

    display_levels.append(DisplayLevel.PUBLIC)
    return display_levels


def graphql_view():
    view_func = GraphQLView.as_view(
        "graphql",
        schema=Schema(query=Query),
        middleware=[authorization_middleware],
        graphiql=bool(config("graphiql", namespace="person_api", default="True")),
    )
    return requires_auth(view_func)


class v2User(Resource):
    """Return a single user."""

    decorators = [requires_auth]

    def get(self, user_id):
        """Return a single user with id `user_id`."""
        user_id = urllib.parse.unquote(user_id)
        parser = reqparse.RequestParser()
        parser.add_argument("Authorization", location="headers")
        parser.add_argument("filterDisplay", type=str)
        args = parser.parse_args()
        scopes = get_scopes(args.get("Authorization"))
        filter_display = args.get("filterDisplay", None)

        if transactions == "false":
            identity_vault = user.Profile(dynamodb_table, dynamodb_client, transactions=False)

        if transactions == "true":
            identity_vault = user.Profile(dynamodb_table, dynamodb_client, transactions=True)

        logger.debug("Attempting to locate a user for: {}".format(user_id))
        if "|" in user_id:
            logger.debug("Searching the vault by user_id for: {}".format(user_id))
            result = identity_vault.find_by_id(user_id)
        elif "@" in user_id:
            logger.debug("Searching the vault by primary_email for: {}".format(user_id))
            result = identity_vault.find_by_email(user_id)
        else:
            return jsonify({})

        if len(result["Items"]) > 0:
            vault_profile = result["Items"][0]["profile"]
            v2_profile = User(user_structure_json=json.loads(vault_profile))
            if "read:fullprofile" in scopes:
                logger.debug("read:fullprofile in token returning the full user profile.")
            else:
                v2_profile.filter_scopes(scope_to_mozilla_data_classification(scopes))

            if "display:all" in scopes:
                logger.debug("display:all in token not filtering profile.")
            else:
                v2_profile.filter_display(scope_to_display_level(scopes))

            if filter_display is not None:
                v2_profile.filter_display(DisplayLevelParms.map(filter_display))

            return jsonify(v2_profile.as_dict())
        else:
            return jsonify({})


class v2Users(Resource):
    """Return a all of the users."""

    decorators = [requires_auth]

    def get(self):
        """Return a single user with id `user_id`."""
        parser = reqparse.RequestParser()
        parser.add_argument("Authorization", location="headers")
        parser.add_argument("nextPage", type=str)
        parser.add_argument("primaryEmail", type=str)
        parser.add_argument("filterDisplay", type=str)
        args = parser.parse_args()

        filter_display = args.get("filterDisplay", None)
        primary_email = args.get("primaryEmail", None)
        next_page = args.get("nextPage", None)
        scopes = get_scopes(args.get("Authorization"))

        if next_page is not None:
            nextPage = load_dirty_json(next_page)
        else:
            nextPage = None

        if transactions == "false":
            identity_vault = user.Profile(dynamodb_table, dynamodb_client, transactions=False)

        if transactions == "true":
            identity_vault = user.Profile(dynamodb_table, dynamodb_client, transactions=True)

        next_page_token = None
        if primary_email is None:
            result = identity_vault.all_by_page(next_page=nextPage, limit=25)
            next_page_token = result.get("LastEvaluatedKey")
        else:
            result = identity_vault.find_by_email(primary_email)
        v2_profiles = []

        for profile in result.get("Items"):
            vault_profile = json.loads(profile.get("profile"))
            v2_profile = User(user_structure_json=vault_profile)
            if "read:fullprofile" in scopes:
                # Assume someone has asked for all the data.
                pass
            else:
                # Assume the we are filtering falls back to public with no scopes
                v2_profile.filter_scopes(scope_to_mozilla_data_classification(scopes))

            if "display:all" in scopes:
                logger.debug("display:all in token not filtering profile.")
            else:
                v2_profile.filter_display(scope_to_display_level(scopes))

            if filter_display is not None:
                v2_profile.filter_display(DisplayLevelParms.map(filter_display))

            v2_profiles.append(v2_profile.as_dict())

        response = {"Items": v2_profiles, "nextPage": next_page_token}
        return jsonify(response)


if config("graphql", namespace="person_api", default="false") == "true":
    app.add_url_rule("/graphql", view_func=graphql_view())

api.add_resource(v2Users, "/v2/users")
api.add_resource(v2User, "/v2/user/<string:user_id>")


@app.route("/v2")
def index():
    return "Mozilla Profile Retrieval Service Endpoint"


def main():
    app.run(host="0.0.0.0", debug=True)


if __name__ == "__main__":
    main()
