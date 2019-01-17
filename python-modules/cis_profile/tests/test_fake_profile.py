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
        u.validate()

    def test_same_fake_user(self):
        u = fake_profile.FakeUser(seed=1337)
        print('generator: 1337', u.user_id.value)
        assert(u.user_id.value is not None)
        # assert specific result

    def test_batch_create(self):
        profiles = fake_profile.batch_create_fake_profiles(seed=1337, count=3)
        assert len(profiles) == 3
        for i, p in enumerate(profiles, 1):
            assert p is not None
            assert p["access_information"]["hris"]["values"]["employee_id"] == i
