import os
import orjson

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
from cis_profile.profile import User
from cis_profile_retrieval_service.advanced import v2UsersByAttrContains
from cis_profile_retrieval_service.common import get_config
from cis_profile_retrieval_service.common import initialize_vault
from cis_profile_retrieval_service.common import get_dynamodb_client
from cis_profile_retrieval_service.common import get_table_resource
from cis_profile_retrieval_service.common import load_dirty_json
from cis_profile_retrieval_service.common import DisplayLevelParms
from cis_profile_retrieval_service.common import scope_to_display_level
from cis_profile_retrieval_service.common import scope_to_mozilla_data_classification
from cis_profile_retrieval_service.common import seed
from cis_profile_retrieval_service.schema import Query
from cis_profile_retrieval_service.schema import AuthorizationMiddleware
from cis_profile_retrieval_service.idp import requires_auth
from cis_profile_retrieval_service.idp import get_scopes
from cis_profile_retrieval_service import __version__


app = Flask(__name__)
api = Api(app)
CORS(
    app,
    allow_headers=(
        "x-requested-with",
        "content-type",
        "accept",
        "origin",
        "authorization",
        "x-csrftoken",
        "withcredentials",
        "cache-control",
        "cookie",
        "session-id",
    ),
    supports_credentials=True,
)
config = get_config()
logger = getLogger(__name__)

cis_environment = config("environment", namespace="cis")

if config("initialize_vault", namespace="person_api", default="false") == "true":
    logger.debug("Initializing vault and pre-seeding it, this will take some time...")
    initialize_vault()
    seed()
    logger.debug("Vault is seeded and ready to go!")


authorization_middleware = AuthorizationMiddleware()
dynamodb_table = get_table_resource()
dynamodb_client = get_dynamodb_client()
transactions = config("transactions", namespace="cis", default="false") == "true"


def graphql_view():
    view_func = GraphQLView.as_view(
        "graphql",
        schema=Schema(query=Query),
        middleware=[authorization_middleware],
        graphiql=bool(config("graphiql", namespace="person_api", default="True")),
    )
    return requires_auth(view_func)


class v2MetadataByPrimaryEmail(Resource):
    """Return the connection method of a user by their primary_email."""

    def get(self, primary_email):
        logger.info("Attempting to get public metadata for primary email: {}".format(primary_email))
        exists_in_cis = exists_in_ldap = False

        identity_vault = user.Profile(dynamodb_table, dynamodb_client, transactions=False)
        result = user.Profile.find_by_email(identity_vault, primary_email)

        if len(result["Items"]) > 0:
            vault_profile = result["Items"][0]["profile"]
            exists_in_cis = True
            exists_in_ldap = User(user_structure_json=orjson.loads(vault_profile)) \
                .as_dict()["access_information"]["ldap"]["values"] is not None

        return jsonify({
            "exists": {
                "cis": exists_in_cis,
                "ldap": exists_in_ldap,
            }
        })


class v2UserByUserId(Resource):
    """Return a single user by user_id."""

    decorators = [requires_auth]

    def get(self, user_id):
        logger.info("Attempting to locate a user for user_id: {}".format(user_id))
        return getUser(user_id, user.Profile.find_by_id)


class v2UserByUuid(Resource):
    """Return a single user by uuid."""

    decorators = [requires_auth]

    def get(self, uuid):
        logger.info("Attempting to locate a user for uuid: {}".format(uuid))
        return getUser(uuid, user.Profile.find_by_uuid)


class v2UserByPrimaryEmail(Resource):
    """Return a single user by primary_email."""

    decorators = [requires_auth]

    def get(self, primary_email):
        logger.info("Attempting to locate a user for primary_email: {}".format(primary_email))
        return getUser(primary_email, user.Profile.find_by_email)


class v2UserByPrimaryUsername(Resource):
    """Return a single user by primary_username."""

    decorators = [requires_auth]

    def get(self, primary_username):
        logger.info("Attempting to locate a user for primary_username: {}".format(primary_username))
        return getUser(primary_username, user.Profile.find_by_username)


class v2UsersByAny(Resource):
    """Return a one page list of user ids, primary email, uuid to support smart publishing."""

    decorators = [requires_auth]

    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument("connectionMethod", type=str, location="args")
        parser.add_argument("active", type=str, location="args")
        parser.add_argument("nextPage", type=str, location="args")

        args = parser.parse_args()

        logger.debug("Arguments received: {}".format(args))

        logger.info("Attempting to get all users for connection method: {}".format(args.get("connectionMethod")))
        next_page = args.get("nextPage")

        identity_vault = user.Profile(dynamodb_table, dynamodb_client, transactions=transactions)

        logger.debug("Getting all users for connection method: {}".format(args.get("connectionMethod")))
        if args.get("active") is not None and args.get("active").lower() == "false":
            active = False
        elif args.get("active") is not None and args.get("active").lower() == "any":
            active = None
        else:
            active = True  # Support returning only active users by default.

        all_users = identity_vault.all_filtered(
            connection_method=args.get("connectionMethod"), active=active, next_page=next_page
        )

        while len(all_users["users"]) == 0 and all_users["nextPage"] is not None:
            # If our result set is zero go get the next page.
            all_users = identity_vault.all_filtered(
                connection_method=args.get("connectionMethod"), active=active, next_page=all_users["nextPage"]
            )

        # Convert vault data to cis-profile-like data format
        all_users_cis = []
        for cuser in all_users["users"]:
            all_users_cis.append(
                {
                    "uuid": cuser["user_uuid"]["S"],
                    "user_id": cuser["id"]["S"],
                    "primary_email": cuser["primary_email"]["S"],
                    "active": cuser["active"]["BOOL"],
                }
            )

        logger.debug("Returning {} users".format(len(all_users_cis)))
        return dict(users=all_users_cis, nextPage=all_users.get("nextPage"))


def getUser(id, find_by):
    """Return a single user with identifier using find_by."""
    id = urllib.parse.unquote(id)
    parser = reqparse.RequestParser()
    parser.add_argument("Authorization", location="headers")
    parser.add_argument("filterDisplay", type=str, location="args")
    parser.add_argument("active", type=str, location="args")
    args = parser.parse_args()
    scopes = get_scopes(args.get("Authorization"))
    filter_display = args.get("filterDisplay", None)

    if args.get("active") is not None and args.get("active").lower() == "false":
        active = False
    elif args.get("active") is not None and args.get("active").lower() == "any":
        active = None
    else:
        active = True

    identity_vault = user.Profile(dynamodb_table, dynamodb_client, transactions=transactions)

    result = find_by(identity_vault, id)

    if len(result["Items"]) > 0:
        vault_profile = result["Items"][0]["profile"]
        v2_profile = User(user_structure_json=orjson.loads(vault_profile))

        if v2_profile.active.value == active or active is None:
            if "read:fullprofile" in scopes:
                logger.debug(
                    "read:fullprofile in token not filtering based on scopes.",
                    extra={"query_args": args, "scopes": scopes},
                )
            else:
                v2_profile.filter_scopes(scope_to_mozilla_data_classification(scopes))

            if "display:all" in scopes:
                logger.debug(
                    "display:all in token not filtering profile based on display.",
                    extra={"query_args": args, "scopes": scopes},
                )
            else:
                v2_profile.filter_display(scope_to_display_level(scopes))

            if filter_display is not None:
                logger.debug(
                    "filter_display argument is passed, applying display level filter.", extra={"query_args": args}
                )
                v2_profile.filter_display(DisplayLevelParms.map(filter_display))

            return jsonify(v2_profile.as_dict())

    logger.debug("No user was found for the query", extra={"query_args": args, "scopes": scopes})
    return jsonify({})


class v2Users(Resource):
    """Return a all of the users."""

    decorators = [requires_auth]

    def get(self):
        """Return a single user with id `user_id`."""
        parser = reqparse.RequestParser()
        parser.add_argument("Authorization", location="headers")
        parser.add_argument("nextPage", type=str, location="args")
        parser.add_argument("primaryEmail", type=str, location="args")
        parser.add_argument("filterDisplay", type=str, location="args")
        parser.add_argument("active", type=str, location="args")

        args = parser.parse_args()

        filter_display = args.get("filterDisplay", None)
        primary_email = args.get("primaryEmail", None)
        next_page = args.get("nextPage", None)
        scopes = get_scopes(args.get("Authorization"))

        logger.info(
            f"Attempting to get paginated users: primary_email:{primary_email}, next_page:{next_page}, "
            "filter_display:{filter_display}, scopes:{scopes}"
        )

        if next_page is not None:
            nextPage = load_dirty_json(next_page)
        else:
            nextPage = None

        identity_vault = user.Profile(dynamodb_table, dynamodb_client, transactions=transactions)

        next_page_token = None
        if primary_email is None:
            result = identity_vault.all_by_page(next_page=nextPage)
            next_page_token = result.get("LastEvaluatedKey")
        else:
            result = identity_vault.find_by_email(primary_email)
        v2_profiles = []

        if args.get("active") is not None and args.get("active").lower() == "false":
            active = False
        else:
            active = True  # Support returning only active users by default.

        for profile in result.get("Items"):
            vault_profile = orjson.loads(profile.get("profile"))
            v2_profile = User(user_structure_json=vault_profile)

            # This must be a pre filtering check because mutation is real.
            if v2_profile.active.value == active:
                allowed_in_list = True
            else:
                allowed_in_list = False

            if "read:fullprofile" in scopes:
                # Assume someone has asked for all the data.
                logger.debug(
                    "The provided token has access to all of the data.", extra={"query_args": args, "scopes": scopes}
                )
                pass
            else:
                # Assume the we are filtering falls back to public with no scopes
                logger.debug("This is a limited scoped query.", extra={"query_args": args, "scopes": scopes})
                v2_profile.filter_scopes(scope_to_mozilla_data_classification(scopes))

            if "display:all" in scopes:
                logger.debug(
                    "display:all in token not filtering profile.", extra={"query_args": args, "scopes": scopes}
                )
            else:
                logger.debug("display filtering engaged for query.", extra={"query_args": args, "scopes": scopes})
                v2_profile.filter_display(scope_to_display_level(scopes))

            if filter_display is not None:
                v2_profile.filter_display(DisplayLevelParms.map(filter_display))

            if allowed_in_list:
                v2_profiles.append(v2_profile.as_dict())
            else:
                logger.debug("Skipping adding this profile to the list of profiles because it is: {}".format(active))
                pass

        response = {"Items": v2_profiles, "nextPage": next_page_token}
        return jsonify(response)


if config("graphql", namespace="person_api", default="false") == "true":
    app.add_url_rule("/graphql", view_func=graphql_view())


api.add_resource(v2Users, "/v2/users")
api.add_resource(v2MetadataByPrimaryEmail, "/v2/user/metadata/<string:primary_email>")
api.add_resource(v2UserByUserId, "/v2/user/user_id/<string:user_id>")
api.add_resource(v2UserByUuid, "/v2/user/uuid/<string:uuid>")
api.add_resource(v2UserByPrimaryEmail, "/v2/user/primary_email/<string:primary_email>")
api.add_resource(v2UserByPrimaryUsername, "/v2/user/primary_username/<string:primary_username>")

# Support batch retrieval of all user ids that are in the system. Make publishing "Smart".
api.add_resource(v2UsersByAny, "/v2/users/id/all")

# Support per attribute query
if config("advanced_search", namespace="person_api", default="false") == "true":
    api.add_resource(v2UsersByAttrContains, "/v2/users/id/all/by_attribute_contains")


@app.route("/v2")
def index():
    return "Mozilla Profile Retrieval Service Endpoint"


@app.route("/v2/version")
def version():
    response = __version__
    return jsonify(message=response)


def main():
    # DEBT: I think this has been fixed in a later version of Flask.
    # We don't call this in production, but instead lean on Serverless' WSGI handler.
    host, _, port = os.environ.get("SERVER_NAME", "127.0.0.1:5000").partition(":")
    port = int(port)
    app.run(host=host, port=port, debug=True)


if __name__ == "__main__":
    main()
