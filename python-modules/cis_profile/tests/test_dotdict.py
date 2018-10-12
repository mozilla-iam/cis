from cis_profile.common import DotDict


class TestDotDict(object):

    def test_dotdict(self):
        x = DotDict({"test": "test"})
        print(x.test)

    def test_dotdict_sublevel(self):
        x = DotDict({"test": {"sub": {"test"}}})
        print(x.test.sub)
