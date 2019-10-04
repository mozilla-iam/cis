"""Support advanced search queries for inclusion in routes via DynamoDb."""
from flask_restful import Resource
from flask_restful import reqparse

from cis_profile_retrieval_service.idp import requires_auth


allowed_advanced_queries = [
    "first_name",
    "fun_title",
    "identities",
    "languages",
    "last_modified",
    "last_name",
    "location",
    "login_method",
    "pgp_public_keys",
    "phone_numbers",
    "picture",
    "primary_email",
    "primary_username",
    "pronouns",
    "schema",
    "ssh_public_keys",
    "tags",
    "timezone",
    "uris",
    "user_id",
    "usernames",
    "uuid",
    "access_information.ldap",
    "access_information.mozilliansorg",
    "access_information.access_provider",
    "access_information.hris",
    "staff_information.cost_center",
    "staff_information.director",
    "staff_information.manager",
    "staff_information.office_location",
    "staff_information.staff",
    "staff_information.team",
    "staff_information.title",
    "staff_information.worker_type",
    "staff_information.wpr_desk_number",
]


class v2UsersByAttrContains(Resource):

    decorators = [requires_auth]

    def get(self):
        parser = reqparse.RequestParser()

        for attr in allowed_advanced_queries:
            # Ensure that only our allowed attributes are parsed.
            parser.add_argument(attr, type=str)

        # args = parser.parse_args()
