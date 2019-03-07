import pytest
from cis_profile import fake_profile
from cis_profile import profile
from cis_profile import exceptions


class TestFakeProfile(object):
    def test_fake_user(self):
        u = fake_profile.FakeUser()
        print(u.user_id.value)
        j = u.as_json()
        d = u.as_dict()
        assert j is not None
        assert d is not None
        assert u.user_id.value is not None
        u.validate()
        u.verify_all_publishers(u)

    def test_same_fake_user(self):
        a = fake_profile.FakeUser(seed=1337)
        b = fake_profile.FakeUser(seed=1337)
        c = fake_profile.FakeUser(seed=23)
        assert a.uuid.value == b.uuid.value
        assert a.uuid.value != c.uuid.value

    def test_batch_create(self):
        profiles = fake_profile.batch_create_fake_profiles(seed=1337, number=3)
        assert len(profiles) == 3
        for i, p in enumerate(profiles, 1):
            assert p is not None
            assert p["access_information"]["hris"]["values"]["employee_id"] == i

    def test_with_and_without_uuid(self):
        c_with_uuid = fake_profile.FakeProfileConfig().uuid_username()
        c_without_uuid = fake_profile.FakeProfileConfig()
        a = fake_profile.FakeUser(seed=23, config=c_with_uuid)
        assert a.uuid.value is not None
        b = fake_profile.FakeUser(seed=23, config=c_without_uuid)
        assert b.uuid.value is None

    def test_null_create_profile(self):
        empty_profile = profile.User()
        create_profile = fake_profile.FakeUser(seed=1337, config=fake_profile.FakeProfileConfig().default().create())
        update_profile = fake_profile.FakeUser(seed=1337, config=fake_profile.FakeProfileConfig().default())

        with pytest.raises(exceptions.PublisherVerificationFailure):
            update_profile.verify_all_publishers(empty_profile)
        assert create_profile.verify_all_publishers(empty_profile) is True
        assert update_profile.verify_all_publishers(create_profile) is True
