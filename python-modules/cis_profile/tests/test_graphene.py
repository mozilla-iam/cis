import cis_profile.graphene as cis_g
import graphene


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
            profile = graphene.Field(cis_g.CoreProfile)

            def resolve_profile(self, info, **kwargs):
                return {}

        schema = graphene.Schema(query=Query)
        r = schema.execute('{}')
        assert r.data is None
