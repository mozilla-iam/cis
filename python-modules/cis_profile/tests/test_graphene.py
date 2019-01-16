from tests import fake_flask_app
from cis_profile.common import DotDict

import cis_profile.graphene as cis_g
import json
import graphene


def json2obj(d):
    # ATTENTION ATTENTION!
    # This looks like nothing but this returns an Object (type: <class '__main__.DotDict'>) because of the `object_hook`
    # not a dict which is a core class (type: <class 'dict'>)
    # graphql will only try to resolve methods IF it's not a dict, so this step is required
    # This trick ensures that the object returned has real methods (while a Dict or a class that is based on dict, like
    # the DotDict does, does not. It uses __getattr__ instead)
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

    def test_graphql_query(self):
        class Query(graphene.ObjectType):
            profile = graphene.Field(cis_g.Profile, user_id=graphene.String(required=True))

            def resolve_profile(self, info, **kwargs):
                fh = open('cis_profile/data/user_profile_null.json')
                user_profile = fh.read()
                fh.close()
                tmp = json2obj(user_profile)
                tmp.first_name.value = 'Hello'
                tmp.user_id.value = 'my_user_id'
                return tmp

        schema = graphene.Schema(Query, auto_camelcase=False)
        result = schema.execute('query getProfile($user_id: String!) {profile(user_id:$user_id) {first_name{value}}}',
                                variables={'user_id': 'my_user_id'})
        print(result.errors, result.data)
        assert result.errors is None
        assert result.data['profile']['first_name']['value'] == 'Hello'

    def test_flask_graphql_query(self):
        class Query(graphene.ObjectType):
            profile = graphene.Field(cis_g.Profile, user_id=graphene.String(required=True))

            def resolve_profile(self, info, **kwargs):
                fh = open('cis_profile/data/user_profile_null.json')
                user_profile = fh.read()
                fh.close()
                tmp = json2obj(user_profile)
                tmp.first_name.value = 'Hello'
                tmp.user_id.value = 'ad|Mozilla-LDAP-Dev|dummymcdummy'
                return tmp

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

        assert result.status_code == 200
        response = json.loads(result.get_data())
        print(response)
        assert response.get('errors') is None
        assert response['data']['profile']['first_name']['value'] == "Hello"
