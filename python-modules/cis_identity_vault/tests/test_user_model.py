import boto3
import json
import os
import uuid
from cis_identity_vault import vault
from cis_profile import FakeUser
from moto import mock_dynamodb2


@mock_dynamodb2
class TestUsersDynalite(object):
    def setup(self):
        os.environ["CIS_ENVIRONMENT"] = "purple"
        os.environ["CIS_REGION_NAME"] = "us-east-1"
        os.environ["DEFAULT_AWS_REGION"] = "us-east-1"
        self.vault_client = vault.IdentityVault()
        self.vault_client.connect()
        self.vault_client.find_or_create()
        self.boto_session = boto3.session.Session(region_name="us-east-1")
        self.dynamodb_resource = self.boto_session.resource("dynamodb")
        self.dynamodb_client = self.boto_session.client("dynamodb")
        self.table = self.dynamodb_resource.Table("purple-identity-vault")

        for x in range(0, 50):  # Must generate 50 users to test paginator
            user_profile = FakeUser().as_dict()
            user_profile["active"]["value"] = True
            uuid = user_profile["uuid"]["value"]
            vault_json_datastructure = {
                "id": user_profile.get("user_id").get("value"),
                "user_uuid": uuid,
                "primary_email": user_profile.get("primary_email").get("value"),
                "primary_username": user_profile.get("primary_username").get("value"),
                "sequence_number": "12345678",
                "profile": json.dumps(user_profile),
                "active": True,
            }
            from cis_identity_vault.models import user

            profile = user.Profile(self.table, self.dynamodb_client, transactions=False)
            profile.create(vault_json_datastructure)

        self.user_profile = FakeUser().as_dict()
        self.user_profile["active"]["value"] = True
        self.uuid = self.user_profile["uuid"]["value"]
        self.vault_json_datastructure = {
            "id": self.user_profile.get("user_id").get("value"),
            "user_uuid": self.uuid,
            "primary_email": self.user_profile.get("primary_email").get("value"),
            "primary_username": self.user_profile.get("primary_username").get("value"),
            "sequence_number": "12345678",
            "profile": json.dumps(self.user_profile),
            "active": True,
        }

    def test_create_method(self):
        from cis_identity_vault.models import user

        profile = user.Profile(self.table, self.dynamodb_client, transactions=False)
        result = profile.create(self.vault_json_datastructure)
        assert result is not None

    def test_delete_method(self):
        from cis_identity_vault.models import user

        profile = user.Profile(self.table, self.dynamodb_client, transactions=False)
        profile.create(self.vault_json_datastructure)
        result = profile.delete(self.vault_json_datastructure)
        assert result is not None

    def test_update_method(self):
        from cis_identity_vault.models import user

        modified_profile = self.user_profile
        modified_profile["primary_email"]["value"] = "dummy@zxy.foo"
        modified_profile["active"]["value"] = True
        modified_profile["phone_numbers"]["values"] = {"foo": ""}
        vault_json_datastructure = {
            "id": modified_profile.get("user_id").get("value"),
            "user_uuid": str(uuid.uuid4()),
            "primary_email": modified_profile.get("primary_email").get("value"),
            "primary_username": self.user_profile.get("primary_username").get("value"),
            "sequence_number": "12345678",
            "profile": json.dumps(modified_profile),
            "active": True,
        }
        profile = user.Profile(self.table, self.dynamodb_client, transactions=False)
        result = profile.update(vault_json_datastructure)
        assert result is not None

    def test_find_user(self):
        from cis_identity_vault.models import user

        primary_email = "dummy@zxy.foo"
        modified_profile = self.user_profile
        modified_profile["primary_email"]["value"] = primary_email
        modified_profile["active"]["value"] = True
        vault_json_datastructure = {
            "id": modified_profile.get("user_id").get("value"),
            "user_uuid": str(uuid.uuid4()),
            "primary_email": modified_profile.get("primary_email").get("value"),
            "primary_username": self.user_profile.get("primary_username").get("value"),
            "sequence_number": "12345678",
            "profile": json.dumps(modified_profile),
            "active": True,
        }
        profile = user.Profile(self.table, self.dynamodb_client, transactions=False)

        profile.update(vault_json_datastructure)

        profile = user.Profile(self.table)
        user_id = self.user_profile.get("user_id").get("value")
        result_for_user_id = profile.find_by_id(user_id)
        result_for_email = profile.find_by_email(primary_email)
        assert result_for_user_id is not None
        assert result_for_email is not None

    def test_find_user_multi_id_for_email(self):
        from cis_identity_vault.models import user

        primary_email = "dummy@zxy.foo"
        modified_profile = self.user_profile
        modified_profile["primary_email"]["value"] = primary_email
        modified_profile["active"]["value"] = True
        vault_json_datastructure_first_id = {
            "id": modified_profile.get("user_id").get("value"),
            "user_uuid": str(uuid.uuid4()),
            "primary_email": modified_profile.get("primary_email").get("value"),
            "primary_username": self.user_profile.get("primary_username").get("value"),
            "sequence_number": "12345678",
            "profile": json.dumps(modified_profile),
            "active": True,
        }

        profile = user.Profile(self.table, self.dynamodb_client, transactions=False)

        profile.update(vault_json_datastructure_first_id)

        vault_json_datastructure_second_id = {
            "id": "foo|mcbar",
            "user_uuid": str(uuid.uuid4()),
            "primary_email": modified_profile.get("primary_email").get("value"),
            "primary_username": self.user_profile.get("primary_username").get("value"),
            "sequence_number": "12345678",
            "profile": json.dumps(modified_profile),
            "active": True,
        }

        profile.update(vault_json_datastructure_second_id)

        profile = user.Profile(self.table)
        self.user_profile.get("user_id").get("value")
        result_for_email = profile.find_by_email(primary_email)
        assert result_for_email is not None
        assert len(result_for_email.get("Items")) > 2

    def test_find_user_multi_id_for_username(self):
        from cis_identity_vault.models import user

        primary_username = "foomcbar123"
        modified_profile = self.user_profile
        modified_profile["primary_username"]["value"] = primary_username
        modified_profile["active"]["value"] = False
        vault_json_datastructure_first_id = {
            "id": modified_profile.get("user_id").get("value"),
            "user_uuid": str(uuid.uuid4()),
            "primary_email": modified_profile.get("primary_email").get("value"),
            "primary_username": self.user_profile.get("primary_username").get("value"),
            "sequence_number": "12345678",
            "profile": json.dumps(modified_profile),
            "active": True,
        }

        profile = user.Profile(self.table, self.dynamodb_client, transactions=False)

        profile.update(vault_json_datastructure_first_id)

        vault_json_datastructure_second_id = {
            "id": "foo|mcbar",
            "user_uuid": str(uuid.uuid4()),
            "primary_email": modified_profile.get("primary_email").get("value"),
            "primary_username": self.user_profile.get("primary_username").get("value"),
            "sequence_number": "12345678",
            "profile": json.dumps(modified_profile),
            "active": True,
        }

        profile.update(vault_json_datastructure_second_id)

        profile = user.Profile(self.table)
        self.user_profile.get("user_id").get("value")
        result_for_username = profile.find_by_username(primary_username)
        assert result_for_username is not None
        assert len(result_for_username.get("Items")) == 2

    def test_find_by_uuid(self):
        from cis_identity_vault.models import user

        profile = user.Profile(self.table, self.dynamodb_client, transactions=False)

        user = json.loads(profile.all[0].get("profile"))

        result_for_uuid = profile.find_by_uuid(user["uuid"]["value"])
        assert len(result_for_uuid.get("Items")) > 0

    def test_find_by_username(self):
        from cis_identity_vault.models import user

        profile = user.Profile(self.table, self.dynamodb_client, transactions=False)

        user = json.loads(profile.all[0].get("profile"))

        result_for_username = profile.find_by_username(user["primary_username"]["value"])
        assert len(result_for_username.get("Items")) > 0

    def test_all_by_filter(self):
        from cis_identity_vault.models import user

        profile = user.Profile(self.table, self.dynamodb_client, transactions=False)
        result = profile.all_filtered(connection_method="email")
        assert len(result) > 0

        result = profile.all_filtered(connection_method="email", active=True)
        assert len(result) > 0
        for record in result:
            assert record["active"]["BOOL"] is True

        result = profile.all_filtered(connection_method="email", active=False)
        for record in result:
            assert record["active"]["BOOL"] is False

    def test_namespace_generator(self):
        pass
        # from cis_identity_vault.models import user
        # profile = user.Profile(self.table, self.dynamodb_client, transactions=False)

        # result = profile.

    def test_find_by_any(self):
        from cis_identity_vault.models import user

        profile = user.Profile(self.table, self.dynamodb_client, transactions=False)
        user_idx = 0
        try:
            sample_user = json.loads(profile.all[user_idx].get("profile"))
            sample_ldap_group = list(sample_user["access_information"]["ldap"]["values"].keys())[0]
        except IndexError:  # Cause sometimes the faker doesn't give an LDAP user.
            user_idx = user_idx + 1
            sample_user = json.loads(profile.all[user_idx].get("profile"))

            while len(
                json.loads(profile.all[user_idx].get("profile")["access_information"]["ldap"]["values"].keys())
            ) == 0:
                user_idx = user_idx + 1

            sample_ldap_group = list(sample_user["access_information"]["ldap"]["values"].keys())[0]
        sample_hris_attr = sample_user["access_information"]["hris"]["values"]["employee_id"]

        # Search by ldap group and return only user IDs
        result = profile.find_by_any(attr="access_information.ldap", comparator=sample_ldap_group)
        assert len(result) > 0
        for this_profile in result["users"]:
            assert this_profile.get("id") is not None

        # Search by ldap group and return user_ids with profiles
        result = profile.find_by_any(attr="access_information.ldap", comparator=sample_ldap_group, full_profiles=True)

        assert len(result) > 0
        # Ensure that our data retrieved contains full profiles
        for this_profile in result["users"]:
            assert this_profile["id"] is not None
            assert this_profile["profile"]["last_name"]["value"] is not None

        # Search by ldap group inverse match and return user_ids with profiles
        result = profile.find_by_any(
            attr="not_access_information.ldap", comparator=sample_ldap_group, full_profiles=True
        )

        # assert result.get("nextPage") is not None

        # Follow the nextPage token and ask for the second page.
        paged_result = profile.find_by_any(
            attr="not_access_information.ldap",
            comparator=sample_ldap_group,
            full_profiles=True,
            next_page=result.get("nextPage"),
        )

        assert paged_result.get("users") is not None

        # Test a search against an hris group
        result = profile.find_by_any(
            attr="access_information.hris.employee_id", comparator=sample_hris_attr, full_profiles=False
        )

        assert result is not None
