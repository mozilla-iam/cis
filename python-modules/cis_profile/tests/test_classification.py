from cis_profile.common import MozillaDataClassification
class TestClassification(object):
    def test_classification(self):
        c = MozillaDataClassification()
        if not 'PUBLIC' in c.public():
            raise(KeyError, 'Incorrect Mozilla Data Classification!')

