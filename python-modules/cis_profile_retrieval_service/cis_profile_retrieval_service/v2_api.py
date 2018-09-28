from flask import Flask
from flask_cors import CORS
from flask_graphql import GraphQLView
from flask_restful import Resource, Api
from graphene import Schema

from cis_profile_retrieval_service import get_config
from cis_profile_retrieval_service import initialize_vault
from cis_profile_retrieval_service import seed
from cis_profile_retrieval_service.schema import Query
from cis_profile_retrieval_service.schema import AuthorizationMiddleware
from cis_profile_retrieval_service.idp import requires_auth
from cis_profile_retrieval_service.idp import requires_scope


app = Flask(__name__)
api = Api(app)
CORS(app)
config = get_config()
initialize_vault()
seed()

authorization_middleware = AuthorizationMiddleware()

def graphql_view():
    view_func = GraphQLView.as_view(
        'graphql',
        schema=Schema(query=Query),
        middleware=[authorization_middleware],
        graphiql=bool(config('graphiql', namespace='person_api', default='True'))
    )
    return requires_auth(view_func)

app.add_url_rule('/graphql', view_func=graphql_view())

def main():
    app.run(host='0.0.0.0', debug=True)

if __name__ == '__main__':
    main()
