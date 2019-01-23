from cis_profile import fake_display


class TestFakeDisplay(object):
    def test_fake_display_empty(self):
        f = fake_display.DisplayFaker()
        profile = {}
        f.populate(profile)
        assert not profile

    def test_fake_display_min(self):
        f = fake_display.DisplayFaker()
        profile = {"user_id": {"metadata": {"display": "private"}}}
        f.populate(profile, policy=fake_display.DisplayFakerPolicy.min_display())
        assert profile["user_id"]["metadata"]["display"] is None

    def test_fake_display_max(self):
        f = fake_display.DisplayFaker()
        profile = {"user_id": {"metadata": {"display": "private"}}}
        f.populate(profile, policy=fake_display.DisplayFakerPolicy.max_display())
        assert profile["user_id"]["metadata"]["display"] == "public"

    def test_fake_display_nested(self):
        f = fake_display.DisplayFaker()
        profile = {"staff_information": {"title": {"metadata": {"display": "staff"}}}}
        f.populate(profile, policy=fake_display.DisplayFakerPolicy.max_display())
        assert profile["staff_information"]["title"]["metadata"]["display"] == "ndaed"
