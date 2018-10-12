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

from cis_identity_vault.models import user
from cis_profile.common import MozillaDataClassification
from cis_profile.profile import User
from cis_profile_retrieval_service.common import get_config
from cis_profile_retrieval_service.common import initialize_vault
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

if config('initialize_vault', namespace='person_api', default='false') == 'true':
    logger.debug('Initializing vault and pre-seeding it, this will take some time...')
    initialize_vault()
    seed()
    logger.debug('Vault is seeded and ready to go!')

authorization_middleware = AuthorizationMiddleware()
dynamodb_table = get_table_resource()


def load_dirty_json(dirty_json):
    regex_replace = [
        (r"([ \{,:\[])(u)?'([^']+)'", r'\1"\3"'), (r" False([, \}\]])", r' false\1'), (r" True([, \}\]])", r' true\1')
    ]
    for r, s in regex_replace:
        dirty_json = re.sub(r, s, dirty_json)
    clean_json = json.loads(dirty_json)
    return clean_json


def scope_to_mozilla_data_classification(scopes):
    classifications = []
    if 'classification:staff' in scopes:
        classifications.append(MozillaDataClassification.STAFF_ONLY)
    elif 'classification:workgroup' in scopes:
        classifications.append(MozillaDataClassification.WORKGROUP_CONFIDENTIAL)
    elif 'classification:individual' in scopes:
        classifications.append(MozillaDataClassification.INDIVIDUAL_CONFIDENTIAL)
    else:
        classifications.append(MozillaDataClassification.PUBLIC)
    return classifications


def graphql_view():
    view_func = GraphQLView.as_view(
        'graphql',
        schema=Schema(query=Query),
        middleware=[authorization_middleware],
        graphiql=bool(config('graphiql', namespace='person_api', default='True'))
    )
    return requires_auth(view_func)


class v2User(Resource):
    """Return a single user."""
    decorators = [requires_auth]

    def get(self, user_id):
        """Return a single user with id `user_id`."""
        parser = reqparse.RequestParser()
        parser.add_argument('Authorization', location='headers')
        scopes = get_scopes(parser.parse_args().get('Authorization'))
        identity_vault = user.Profile(dynamodb_table)
        result = identity_vault.find_by_id(user_id)
        vault_profile = result.get('profile')
        v2_profile = User(user_structure_json=vault_profile)
        if len(scopes) == 1 and 'read:fullprofile' in scopes:
            pass
        else:
            v2_profile.filter_scopes(scope_to_mozilla_data_classification(scopes))
        return jsonify(v2_profile.as_dict())


class v2Users(Resource):
    """Return a all of the users."""
    decorators = [requires_auth]

    def get(self):
        """Return a single user with id `user_id`."""
        parser = reqparse.RequestParser()
        parser.add_argument('Authorization', location='headers')
        parser.add_argument('nextPage', type=str)
        parser.add_argument('primaryEmail', type=str)

        primary_email = parser.parse_args().get('primaryEmail')
        next_page = parser.parse_args().get('nextPage')
        scopes = get_scopes(parser.parse_args().get('Authorization'))

        if next_page is not None:
            nextPage = load_dirty_json(next_page)
        else:
            nextPage = None

        identity_vault = user.Profile(dynamodb_table)

        if primary_email is None:
            result = identity_vault.all_by_page(next_page=nextPage, limit=25)
            next_page_token = result.get('LastEvaluatedKey')
        else:
            result = identity_vault.find_by_email(primary_email)
        v2_profiles = []

        for profile in result.get('Items'):
            vault_profile = json.loads(profile.get('profile'))
            v2_profile = User(user_structure_json=vault_profile)
            if len(scopes) == 1 and 'read:fullprofile' in scopes:
                # Assume someone has asked for all the data.
                pass
            else:
                # Assume the we are filtering falls back to public with no scopes
                v2_profile.filter_scopes(scope_to_mozilla_data_classification(scopes))
            v2_profiles.append(v2_profile.as_dict())
            next_page_token = result.get('LastEvaluatedKey')

        response = {'Items': v2_profiles, 'nextPage': next_page_token}
        return jsonify(response)


if config('graphql', namespace='person_api', default='false') == 'true':
    app.add_url_rule('/graphql', view_func=graphql_view())

api.add_resource(v2Users, '/v2/users')
api.add_resource(v2User, '/v2/user/<string:user_id>')


def main():
    app.run(host='0.0.0.0', debug=True)


if __name__ == '__main__':
    main()
