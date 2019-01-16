import json

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

from cis_hris_api import common
from cis_hris_api import idp
from cis_hris_api.schema import AuthorizationMiddleware
from cis_hris_api.schema import Query


app = Flask(__name__)
api = Api(app)
CORS(app)
config = common.get_config()
logger = getLogger(__name__)

authorization_middleware = AuthorizationMiddleware()
dynamodb_table = common.get_table_resource()


def graphql_view():
    view_func = GraphQLView.as_view(
        'graphql',
        schema=Schema(query=Query, auto_camelcase=False),
        middleware=[authorization_middleware],
        graphiql=bool(config('graphiql', namespace='hris_api', default='True'))
    )
    return idp.requires_auth(view_func)


app.add_url_rule('/graphql', view_func=graphql_view())


@app.route('/')
def index():
    return 'Mozilla HRIS API Endpoint'


def main():
    app.run(host='0.0.0.0', debug=True)


if __name__ == '__main__':
    main()
