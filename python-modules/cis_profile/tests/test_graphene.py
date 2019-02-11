from tests import fake_flask_app
from cis_profile.common import DotDict
from cis_profile.common import DisplayLevel
from cis_profile import fake_profile

import cis_profile.graphene as cis_g
import json
import graphene


class TestGraphene(object):
    def test_schema_initializes_union(self):
        class Query(graphene.ObjectType):
            profile = graphene.Field(cis_g.Profile)

            def resolve_profile(self, info, **kwargs):
                return {}

        schema = graphene.Schema(query=Query)
        r = schema.execute("{}")
        assert r.data is None

    def test_schema_initializes_core(self):
        class Query(graphene.ObjectType):
            profile = graphene.Field(cis_g.Profile)

            def resolve_profile(self, info, **kwargs):
                return {}

        schema = graphene.Schema(query=Query)
        r = schema.execute("{}")
        assert r.data is None

    def test_graphql_query(self):
        fake_user = fake_profile.FakeUser(seed=1337)

        class Query(graphene.ObjectType):
            profile = graphene.Field(cis_g.Profile, user_id=graphene.String(required=True))

            def resolve_profile(self, info, **kwargs):
                return fake_user

        schema = graphene.Schema(Query, auto_camelcase=False)
        result = schema.execute(
            "query getProfile($user_id: String!) {profile(user_id:$user_id) {uuid{value}}}",
            variables={"user_id": fake_user.user_id.value},
        )
        assert result.errors is None
        assert result.data["profile"]["uuid"]["value"] == fake_user.uuid.value

    def test_graphql_query_filtered(self):
        fake_user = fake_profile.FakeUser(seed=1337)
        fake_user.filter_display()

        class Query(graphene.ObjectType):
            profile = graphene.Field(cis_g.Profile, uuid=graphene.String(required=True))

            def resolve_profile(self, info, **kwargs):
                return fake_user

        schema = graphene.Schema(Query, auto_camelcase=False)
        result = schema.execute(
            "query getProfile($uuid: String!) {profile(uuid:$uuid) {uuid{value} staff_information{title{value}}}}",
            variables={"uuid": fake_user.uuid.value},
        )
        assert result.errors is None
        assert result.data["profile"]["uuid"]["value"] == fake_user.uuid.value
        assert result.data["profile"]["staff_information"]["title"] is None

    def test_flask_graphql_query(self):
        fake_user = fake_profile.FakeUser(seed=1337)
        print(fake_user.user_id.value)

        class Query(graphene.ObjectType):
            profile = graphene.Field(cis_g.Profile, user_id=graphene.String(required=True))

            def resolve_profile(self, info, **kwargs):
                return fake_user

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
        payload = 'query {{profile (user_id:"{}") {{first_name{{value}}}}}}'.format(fake_user.user_id.value)
        result = app.get("/graphql?query={}".format(payload), follow_redirects=True)

        assert result.status_code == 200
        response = json.loads(result.get_data())
        print(response)
        assert response.get("errors") is None
        assert response["data"]["profile"]["first_name"]["value"] == fake_user.first_name.value
