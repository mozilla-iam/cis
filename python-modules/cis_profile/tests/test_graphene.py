from tests import fake_flask_app
from cis_profile.common import DotDict

import cis_profile.graphene as cis_g
import json
import graphene


def json2obj(d):
    return json.loads(d, object_hook=DotDict)


class TestGraphene(object):
    def test_schema_initializes_union(self):
        class Query(graphene.ObjectType):
            profile = graphene.Field(cis_g.Profile)

            def resolve_profile(self, info, **kwargs):
                return {}

        schema = graphene.Schema(query=Query)
        r = schema.execute('{}')
        assert r.data is None

    def test_schema_initializes_core(self):
        class Query(graphene.ObjectType):
            profile = graphene.Field(cis_g.Profile)

            def resolve_profile(self, info, **kwargs):
                return {}

        schema = graphene.Schema(query=Query)
        r = schema.execute('{}')
        assert r.data is None

    def test_flask_graphql_query(self):
        class Query(graphene.ObjectType):
            profile = graphene.Field(cis_g.Profile, user_id=graphene.String(required=True))

            def resolve_profile(self, info, **kwargs):
                fh = open('cis_profile/data/user_profile_null.json')
                user_profile = fh.read()
                fh.close()
                return json2obj(user_profile)

        # The following code may be used to test for scopes in the JWT token
        # However, we're not doing this right now (and we may never need it, but if we do, it's here!)
        # See fake_auth0.py in cis modules
        # f = FakeBearer()
        # token = f.generate_bearer_without_scope()
        # app.get(...       headers={
        #            'Authorization': 'Bearer ' + token
        #            },

        app = fake_flask_app.app
        fake_flask_app.add_rule(Query)
        app.testing = True
        app = app.test_client()
        payload = 'query {profile (user_id:"ad|Mozilla-LDAP-Dev|dummymcdummy") {first_name{value}}}'
        result = app.get('/graphql?query={}'.format(payload),
                         follow_redirects=True)

        response = json.loads(result.get_data())
        print(response)
        assert response['data']['profile']['first_name']['value'] is None
