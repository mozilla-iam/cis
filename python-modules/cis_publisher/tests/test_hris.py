import cis_publisher
import cis_profile
import logging
import json
import mock

# from moto import mock_lambda
## import boto3

logging.getLogger("cis_publisher").setLevel(logging.INFO)


class TestHRIS(object):
    def test_parse_hris(self):
        hris_data = {}
        with open("tests/fixture/workday.json") as fd:
            hris_data = json.load(fd)

        hris = cis_publisher.hris.HRISPublisher()
        profiles = hris.convert_hris_to_cis_profiles(
            hris_data,
            {"ad|Mozilla-LDAP|NDonna": "ndonna@mozilla.com", "ad|Mozilla-LDAP|flastname": "flastnamehere@mozilla.com"},
            {"ndonna@mozilla.com": "ad|Mozilla-LDAP|NDonna", "flastnamehere@mozilla.com": "ad|mozilla-LDAP|flastname"},
            user_ids=["ad|Mozilla-LDAP|NDonna"],
        )

        print("parsed {} profiles".format(len(profiles)))

        # Check access information is populated
        assert profiles[0].access_information.hris["values"]["employee_id"] == "31337"

        c = 0
        # Verify data consistency
        for p in profiles:
            assert p.primary_email.value is not None
            if hris_data["Report_Entry"][c]["IsManager"] == "TRUE":
                assert p.staff_information.manager.value is True
            else:
                assert p.staff_information.manager.value is False

            # Just info for debugging
            d = p.as_dict()
            si = {}
            for i in d["staff_information"]:
                si[i] = d["staff_information"][i]["value"]
            print(p.primary_email.value, p.last_name.value, d["access_information"]["hris"]["values"], si)

            for i in d["access_information"]["hris"]["values"]:
                si[i] = d["access_information"]["hris"]["values"]
            print(si)
            c = c + 1

    def test_single_user_id(self):
        hris_data = {}
        with open("tests/fixture/workday.json") as fd:
            hris_data = json.load(fd)

        hris = cis_publisher.hris.HRISPublisher()
        profiles = hris.convert_hris_to_cis_profiles(
            hris_data,
            {"ad|Mozilla-LDAP|NDonna": "ndonna@mozilla.com", "ad|Mozilla-LDAP|flastname": "flastnamehere@mozilla.com"},
            {"ndonna@mozilla.com": "ad|Mozilla-LDAP|NDonna", "flastnamehere@mozilla.com": "ad|mozilla-LDAP|flastname"},
            user_ids=["ad|Mozilla-LDAP|NDonna"],
        )
        assert profiles[0].access_information.hris["values"]["employee_id"] == "31337"

    @mock.patch("cis_publisher.Publish.get_cis_user")
    def test_user_deactivate(self, mock_cis_user):
        hris_data = {}
        with open("tests/fixture/workday.json") as fd:
            hris_data = json.load(fd)

        def side_effect(*args, **kwargs):
            fake_user = cis_profile.User(user_id=args[0])
            if args[0] == "ad|Mozilla-LDAP|community":
                fake_user.staff_information.staff.value = False
            else:
                fake_user.staff_information.staff.value = True
            return fake_user

        mock_cis_user.side_effect = side_effect

        hris = cis_publisher.hris.HRISPublisher()
        publisher = cis_publisher.Publish([], login_method="ad", publisher_name="hris")
        # we pass 2 fake users, ndonna is in the fixture, nolongerexist is not in the fixture but "CIS" "has it"
        publisher.known_cis_users_by_user_id = {
            "ad|Mozilla-LDAP|NDonna": "ndonna@mozilla.com",
            "ad|Mozilla-LDAP|notexist": "nolongerexists@mozilla.com",
            "ad|Mozilla-LDAP|community": "community@community.net",
        }
        publisher.known_cis_users_by_email = {
            "ndonna@mozilla.com": "ad|Mozilla-LDAP|NDonna",
            "nolongerexists@mozilla.com": "ad|Mozilla-LDAP|notexist",
            "community@community.net": "ad|Mozilla-LDAP|community",
        }
        for uid in publisher.known_cis_users_by_user_id:
            p = cis_profile.User(user_id=uid, primary_email=publisher.known_cis_users_by_user_id[uid])
            if uid == "ad|Mozilla-LDAP|community":
                p.staff_information.staff.value = False
            else:
                p.staff_information.staff.value = True
            publisher.all_known_profiles[uid] = p

        profiles = hris.convert_hris_to_cis_profiles(
            hris_data,
            publisher.known_cis_users_by_user_id,
            publisher.known_cis_users_by_email,
            user_ids=["ad|Mozilla-LDAP|NDonna", "ad|Mozilla-LDAP|notexist", "ad|Mozilla-LDAP|community"],
        )
        profiles = hris.deactivate_users(publisher, profiles, hris_data)
        # nolongerexist is returned by fake cis reply, but is not in hris workday fixture, so it should be active.value
        # = false
        # Community doesnt exist in HRIS but should not be touched so we should have 2 profiles back (ie community is
        # excluded)
        assert len(profiles) == 2
        assert profiles[1].active.value is False
        assert profiles[1].primary_email.value == "nolongerexists@mozilla.com"
        assert profiles[0].active.value is True
        assert profiles[0].primary_email.value == "ndonna@mozilla.com"


# Not yet supported by moto
#    def test_reentrancy(self):
#        hris_data = {}
#        with open("tests/fixture/workday.json") as fd:
#            hris_data = json.load(fd)
#
#        hris = cis_publisher.hris.HRISPublisher(context={"function_name": "test"})
#        hris.publish()
