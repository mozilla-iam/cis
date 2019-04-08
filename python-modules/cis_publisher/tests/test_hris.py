import cis_publisher

# from moto import mock_lambda
## import boto3
import json


class TestHRIS(object):
    def test_parse_hris(self):
        hris_data = {}
        with open("tests/fixture/workday.json") as fd:
            hris_data = json.load(fd)

        hris = cis_publisher.hris.HRISPublisher()
        profiles = hris.convert_hris_to_cis_profiles(hris_data, user_ids=None)
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
            {
                "ndonna@mozilla.com": "ad|Mozilla-LDAP-Dev|NDonna",
                "flastnamehere@mozilla.com": "ad|mozilla-LDAP-Dev|flastname",
            },
            user_ids=["ad|Mozilla-LDAP-Dev|NDonna"],
        )
        assert profiles[0].access_information.hris["values"]["employee_id"] == "31337"


# Not yet supported by moto
#    def test_reentrancy(self):
#        hris_data = {}
#        with open("tests/fixture/workday.json") as fd:
#            hris_data = json.load(fd)
#
#        hris = cis_publisher.hris.HRISPublisher(context={"function_name": "test"})
#        hris.publish()
