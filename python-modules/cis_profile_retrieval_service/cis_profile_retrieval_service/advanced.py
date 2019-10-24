"""Support advanced search queries for inclusion in routes via DynamoDb."""
from flask_restful import Resource
from flask_restful import reqparse


from cis_profile_retrieval_service.idp import requires_auth
from cis_identity_vault.models import user
from cis_profile_retrieval_service.common import get_config
from cis_profile_retrieval_service.common import get_dynamodb_client
from cis_profile_retrieval_service.common import get_table_resource
from cis_profile_retrieval_service.idp import requires_auth
from cis_profile_retrieval_service.idp import get_scopes


dynamodb_table = get_table_resource()
dynamodb_client = get_dynamodb_client()
transactions = config("transactions", namespace="cis", default="false")


allowed_advanced_queries = [
    "active",
    "access_information.ldap",
    "access_information.mozilliansorg",
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

        if transactions == "false":
            identity_vault = user.Profile(dynamodb_table, dynamodb_client, transactions=False)

        if transactions == "true":
            identity_vault = user.Profile(dynamodb_table, dynamodb_client, transactions=True)

        next_page = args.get('nextPage', None)
        full_profiles = args.get('fullProfiles', None)

        if full_profiles is not None:
            full_profiles = bool(full_profiles)

        for attr in allowed_advanced_queries:
            # Ensure that only our allowed attributes are parsed.
            parser.add_argument(attr, type=str)

        if args.get('active', True):
            # Default to filtering on only active users
            active = True
        else:
            active = False

        # determine which arg was passed in from the whitelist and then set it up
        for k, v in args:
            if k != 'active' or k != 'nextPage' or k != 'fullProfiles':
                if k is not None:
                    attr = k
            comparator = args.get(k)

        result = identity_vault.find_by_any(
            attr, comparator, next_page, full_profiles
        )

        return result
