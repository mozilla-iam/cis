import os
from moto import mock_ssm
from cis_profile import FakeUser


@mock_ssm
class TestRDS(object):
    def setup(self, *args):
        os.environ["CIS_ENVIRONMENT"] = "testing"
        os.environ["CIS_REGION_NAME"] = "us-east-1"
        os.environ["DEFAULT_AWS_REGION"] = "us-east-1"

        # Mock a user profile using the faker to send to the database.
        self.user_profile = FakeUser().as_dict()

    def test_table_init(self):
        os.environ["CIS_POSTGRES_HOST"] = "db"
        os.environ["CIS_POSTGRES_PORT"] = "5432"
        os.environ["CIS_DB_USER"] = "cis_user"
        os.environ["CIS_DB_PASSWORD"] = "testing"
        from cis_identity_vault import vault

        v = vault.RelationalIdentityVault()
        v.create()
        assert v.table() is not None
        v.delete()

    def test_db_create(self):
        os.environ["CIS_POSTGRES_HOST"] = "db"
        os.environ["CIS_POSTGRES_PORT"] = "5432"
        os.environ["CIS_DB_USER"] = "cis_user"
        os.environ["CIS_DB_PASSWORD"] = "testing"
        os.environ["CIS_IDENTITY_VAULT"] = "purple-unicorn"
        from cis_identity_vault import vault

        v = vault.RelationalIdentityVault()
        v.find_or_create()
        v.delete()

    def test_user_create(self):
        os.environ["CIS_POSTGRES_HOST"] = "db"
        os.environ["CIS_POSTGRES_PORT"] = "5432"
        os.environ["CIS_DB_USER"] = "cis_user"
        os.environ["CIS_DB_PASSWORD"] = "testing"
        from cis_identity_vault import vault
        from cis_identity_vault.models import user

        v = vault.RelationalIdentityVault()
        v.create()
        u = user.ProfileRDS()
        res = u.create(user_profile=self.user_profile)
        u.delete(user_profile=self.user_profile)
        assert res is not None
        v.delete()

    def test_user_find(self):
        os.environ["CIS_POSTGRES_HOST"] = "db"
        os.environ["CIS_POSTGRES_PORT"] = "5432"
        os.environ["CIS_DB_USER"] = "cis_user"
        os.environ["CIS_DB_PASSWORD"] = "testing"
        from cis_identity_vault import vault
        from cis_identity_vault.models import user

        v = vault.RelationalIdentityVault()
        v.create()
        u = user.ProfileRDS()
        res = u.create(user_profile=self.user_profile)
        positive_search_result = u.find(self.user_profile)
        assert positive_search_result is not None
        non_existant_user = FakeUser().as_dict()
        negative_search_result = u.find(non_existant_user)
        assert negative_search_result is None
        u.delete(user_profile=self.user_profile)
        assert res is not None
        v.delete()

    def test_user_delete(self):
        os.environ["CIS_POSTGRES_HOST"] = "db"
        os.environ["CIS_POSTGRES_PORT"] = "5432"
        os.environ["CIS_DB_USER"] = "cis_user"
        os.environ["CIS_DB_PASSWORD"] = "testing"
        from cis_identity_vault import vault
        from cis_identity_vault.models import user

        v = vault.RelationalIdentityVault()
        v.create()
        u = user.ProfileRDS()
        u.create(user_profile=self.user_profile)
        u.delete(user_profile=self.user_profile)
        assert u.find(self.user_profile) is None

    def test_user_update(self):
        os.environ["CIS_POSTGRES_HOST"] = "db"
        os.environ["CIS_POSTGRES_PORT"] = "5432"
        os.environ["CIS_DB_USER"] = "cis_user"
        os.environ["CIS_DB_PASSWORD"] = "testing"
        from cis_identity_vault import vault
        from cis_identity_vault.models import user

        v = vault.RelationalIdentityVault()
        v.create()
        u = user.ProfileRDS()
        u.create(user_profile=self.user_profile)
        mutated_user_profile = self.user_profile
        mutated_user_profile["active"]["value"] = False
        u.update(user_profile=mutated_user_profile)
        u.delete(user_profile=self.user_profile)

    def test_find_by_email(self):
        os.environ["CIS_POSTGRES_HOST"] = "db"
        os.environ["CIS_POSTGRES_PORT"] = "5432"
        os.environ["CIS_DB_USER"] = "cis_user"
        os.environ["CIS_DB_PASSWORD"] = "testing"
        from cis_identity_vault import vault
        from cis_identity_vault.models import user

        v = vault.RelationalIdentityVault()
        v.create()
        u = user.ProfileRDS()
        self.user_profile["primary_email"]["value"] = "bob@bob.com"
        u.create(user_profile=self.user_profile)
        primary_email = self.user_profile["primary_email"]["value"]
        s = user.ProfileRDS()
        search_result = s.find_by_email(primary_email)
        assert len(search_result) > 0

    def test_find_by_uuid(self):
        os.environ["CIS_POSTGRES_HOST"] = "db"
        os.environ["CIS_POSTGRES_PORT"] = "5432"
        os.environ["CIS_DB_USER"] = "cis_user"
        os.environ["CIS_DB_PASSWORD"] = "testing"
        from cis_identity_vault import vault
        from cis_identity_vault.models import user

        v = vault.RelationalIdentityVault()
        v.create()
        u = user.ProfileRDS()
        u.create(user_profile=self.user_profile)
        s = user.ProfileRDS()
        search_result = s.find_by_uuid(self.user_profile["uuid"]["value"])
        assert search_result.profile["uuid"]["value"] == self.user_profile["uuid"]["value"]

    def test_find_by_primary_username(self):
        os.environ["CIS_POSTGRES_HOST"] = "db"
        os.environ["CIS_POSTGRES_PORT"] = "5432"
        os.environ["CIS_DB_USER"] = "cis_user"
        os.environ["CIS_DB_PASSWORD"] = "testing"
        from cis_identity_vault import vault
        from cis_identity_vault.models import user

        v = vault.RelationalIdentityVault()
        v.create()
        u = user.ProfileRDS()
        u.create(user_profile=self.user_profile)
        s = user.ProfileRDS()
        search_result = s.find_by_username(self.user_profile["primary_username"]["value"])
        assert search_result.profile["primary_username"]["value"] == self.user_profile["primary_username"]["value"]
