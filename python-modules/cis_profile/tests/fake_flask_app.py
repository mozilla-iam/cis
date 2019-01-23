from flask import Flask
from flask_graphql import GraphQLView
from flask_restful import Api
from graphene import Schema

app = Flask(__name__)
api = Api(app)


def graphql_view(Query):
    view_func = GraphQLView.as_view("graphql", schema=Schema(query=Query, auto_camelcase=False), graphiql=True)
    return view_func


def add_rule(query):
    app.add_url_rule("/graphql", view_func=graphql_view(query))
