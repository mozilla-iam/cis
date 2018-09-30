from cis_profile.common import MozillaDataClassification


class TestClassification(object):
    def test_classification(self):
        c = MozillaDataClassification()
        if 'PUBLIC' not in c.public():
            raise(KeyError, 'Incorrect Mozilla Data Classification!')
