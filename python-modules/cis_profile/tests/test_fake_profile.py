from cis_profile import fake_profile


class TestFakeProfile(object):

    def test_fake_user(self):
        u = fake_profile.FakeUser()
        print(u.user_id.value)
        j = u.as_json()
        d = u.as_dict()
        assert(j is not None)
        assert(d is not None)
        assert(u.user_id.value is not None)

    def test_same_fake_user(self):
        u = fake_profile.FakeUser(generator=1337)
        print('generator: 1337', u.user_id.value)
        assert(u.user_id.value is not None)
        # assert specific result
