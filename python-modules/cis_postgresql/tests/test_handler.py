import boto3
import json
import os
import sqlalchemy
import uuid
from copy import deepcopy
from moto import mock_dynamodb2

from boto3.dynamodb.types import TypeDeserializer
from cis_postgresql import exchange
from cis_profile import FakeUser


class EventGenerator(object):
    """Use our schema scaffold to fake an event from the dynamodb stream."""

    def __init__(self):
        fh = open("tests/fixture/dynamodb-event.json")
        self.event_schema = json.loads(fh.read())["Records"]
        fh.close()
        self.users = None
        self.deserializer = TypeDeserializer()

    def _generate_fake_users(self):
        users = []
        for i in range(0, 10):
            cis_profile_object = FakeUser()
            user_profile = cis_profile_object.as_dict()
            users.append(
                {
                    "id": user_profile["user_id"]["value"],
                    "user_uuid": user_profile["uuid"]["value"],
                    "profile": json.dumps(user_profile),
                    "primary_email": user_profile["primary_email"]["value"],
                    "primary_username": user_profile["primary_username"]["value"],
                    "sequence_number": str(uuid.uuid4().int),
                    "active": user_profile["active"]["value"],
                    "flat_profile": {
                        k: self.deserializer.deserialize(v) for k, v in cis_profile_object.as_dynamo_flat_dict().items()
                    },
                }
            )
        self.users = users

    def event(self):
        self._generate_fake_users()
        event = {"Records": []}

        for user in self.users:
            this_record = deepcopy(self.event_schema[0])
            this_record["dynamodb"]["Keys"]["id"]["S"] = user["id"]
            event["Records"].append(this_record)
        return event

    def events_and_users(self):
        self._generate_fake_users()
        event = {"Records": []}

        for user in self.users:
            this_record = deepcopy(self.event_schema[0])
            this_record["dynamodb"]["Keys"]["id"]["S"] = user["id"]
            event["Records"].append(this_record)
        return dict(event=event, users=self.users)


@mock_dynamodb2
class TestEventHandler(object):
    def setup(self):
        fh = open("tests/fixture/dynamodb-event.json")
        # Event data structure to load in order to mock a profile update
        self.event_json = fh.read()
        fh.close()
        self.event_gen = EventGenerator()

        from cis_identity_vault import vault

        self.v = vault.IdentityVault()
        os.environ["CIS_ENVIRONMENT"] = "testing"
        os.environ["CIS_REGION_NAME"] = "us-east-1"
        os.environ["DEFAULT_AWS_REGION"] = "us-east-1"
        self.v.connect()
        result = self.v.find_or_create()
        assert result is not None
        self.v.tag_vault()
        self.event_gen = EventGenerator()
        self.events_and_users = self.event_gen.events_and_users()

        os.environ["CIS_POSTGRES_HOST"] = "db"
        os.environ["CIS_POSTGRES_PORT"] = "5432"
        os.environ["CIS_DB_USER"] = "cis_user"
        os.environ["CIS_DB_PASSWORD"] = "testing"

        q = vault.RelationalIdentityVault()
        q.session()
        q.create()

    def seed_fake_users(self):
        from cis_identity_vault.models import user

        u = user.Profile(
            dynamodb_table_resource=boto3.resource("dynamodb", region_name="us-east-1").Table("testing-identity-vault"),
            dynamodb_client=boto3.client("dynamodb", region_name="us-east-1"),
            transactions=False,
        )
        u.create_batch(self.events_and_users["users"])

    def test_profile_base(self):
        fake_user = FakeUser()
        exch = exchange.ProfileBase()
        exch.user_structure_json = fake_user.as_dict()
        assert exch.valid is True
        assert fake_user.as_dict() == exch.cis_profile.as_dict()

    def test_event_generator(self):
        e = EventGenerator()
        assert e.event() is not None
        assert len(e.event()["Records"]) == 10

    def test_dynamo_stream(self):
        os.environ["CIS_ENVIRONMENT"] = "testing"
        os.environ["CIS_REGION_NAME"] = "us-east-1"
        os.environ["DEFAULT_AWS_REGION"] = "us-east-1"
        os.environ["CIS_DYNAMODB_ARN"] = boto3.client("dynamodb", region_name="us-east-1").describe_table(
            TableName="testing-identity-vault"
        )["Table"]["TableArn"]
        from cis_identity_vault import vault

        self.v = vault.IdentityVault()
        os.environ["CIS_ENVIRONMENT"] = "testing"
        os.environ["CIS_REGION_NAME"] = "us-east-1"
        os.environ["DEFAULT_AWS_REGION"] = "us-east-1"
        self.v.connect()
        result = self.v.find_or_create()
        assert result is not None
        self.v.tag_vault()
        self.seed_fake_users()
        exch = exchange.DynamoStream()
        user_ids = exch.user_ids_from_stream(self.events_and_users["event"])
        assert user_ids is not None
        profiles = exch.profiles(user_ids)
        assert profiles is not None

    def test_postgresql_writes(self):
        os.environ["CIS_ENVIRONMENT"] = "testing"
        os.environ["CIS_REGION_NAME"] = "us-east-1"
        os.environ["DEFAULT_AWS_REGION"] = "us-east-1"
        os.environ["CIS_DYNAMODB_ARN"] = boto3.client("dynamodb", region_name="us-east-1").describe_table(
            TableName="testing-identity-vault"
        )["Table"]["TableArn"]
        from cis_identity_vault import vault

        self.v = vault.IdentityVault()
        os.environ["CIS_ENVIRONMENT"] = "testing"
        os.environ["CIS_REGION_NAME"] = "us-east-1"
        os.environ["DEFAULT_AWS_REGION"] = "us-east-1"

        os.environ["CIS_POSTGRES_HOST"] = "db"
        os.environ["CIS_POSTGRES_PORT"] = "5432"
        os.environ["CIS_DB_USER"] = "cis_user"
        os.environ["CIS_DB_PASSWORD"] = "testing"
        self.v.connect()
        result = self.v.find_or_create()
        self.v.tag_vault()
        self.seed_fake_users()
        exch = exchange.DynamoStream()
        user_ids = exch.user_ids_from_stream(self.events_and_users["event"])
        profiles = exch.profiles(user_ids)

        postgres_vault = exchange.PostgresqlMapper()
        result = postgres_vault.to_postgres(profiles)
        assert len(result) == len(profiles)

    def test_postgresql_writes_for_all(self):
        os.environ["CIS_ENVIRONMENT"] = "testing"
        os.environ["CIS_REGION_NAME"] = "us-east-1"
        os.environ["DEFAULT_AWS_REGION"] = "us-east-1"
        os.environ["CIS_DYNAMODB_ARN"] = boto3.client("dynamodb", region_name="us-east-1").describe_table(
            TableName="testing-identity-vault"
        )["Table"]["TableArn"]
        from cis_identity_vault import vault

        self.v = vault.IdentityVault()
        os.environ["CIS_ENVIRONMENT"] = "testing"
        os.environ["CIS_REGION_NAME"] = "us-east-1"
        os.environ["DEFAULT_AWS_REGION"] = "us-east-1"

        os.environ["CIS_POSTGRES_HOST"] = "db"
        os.environ["CIS_POSTGRES_PORT"] = "5432"
        os.environ["CIS_DB_USER"] = "cis_user"
        os.environ["CIS_DB_PASSWORD"] = "testing"
        self.v.connect()
        result = self.v.find_or_create()
        self.v.tag_vault()
        self.seed_fake_users()
        exch = exchange.DynamoStream()
        user_ids = None
        profiles = exch.profiles(user_ids)
        postgres_vault = exchange.PostgresqlMapper()
        result = postgres_vault.to_postgres(profiles)
        assert len(result) == len(profiles)

    def test_query_interfaces(self):
        os.environ["CIS_ENVIRONMENT"] = "testing"
        os.environ["CIS_REGION_NAME"] = "us-east-1"
        os.environ["DEFAULT_AWS_REGION"] = "us-east-1"
        os.environ["CIS_DYNAMODB_ARN"] = boto3.client("dynamodb", region_name="us-east-1").describe_table(
            TableName="testing-identity-vault"
        )["Table"]["TableArn"]
        from cis_identity_vault import vault

        self.v = vault.IdentityVault()
        os.environ["CIS_POSTGRES_HOST"] = "db"
        os.environ["CIS_POSTGRES_PORT"] = "5432"
        os.environ["CIS_DB_USER"] = "cis_user"
        os.environ["CIS_DB_PASSWORD"] = "testing"
        self.v.connect()
        self.v.find_or_create()
        self.v.tag_vault()
        self.seed_fake_users()

        exch = exchange.DynamoStream()
        user_ids = None
        profiles = exch.profiles(user_ids)

        postgres_vault = exchange.PostgresqlMapper()
        postgres_vault.to_postgres(profiles)

        from cis_postgresql import execute
        from cis_identity_vault.vault import RelationalIdentityVault

        r = RelationalIdentityVault()
        query = execute.raw_query(r.session(), "select * from people")
        assert query is not None
        query = execute.sql_alchemy_select(r.engine(), "active", "True", "contains")
        assert len(query) > 0
        query = execute.sql_alchemy_select(r.engine(), "active", "True", "contains")

        # Test the grouping functionality
        from cis_identity_vault.models import rds

        Session = sqlalchemy.orm.sessionmaker(bind=r.session())
        session = Session()
        q = session.query(rds.People)
        valid_sample_user = q.filter().all()[0]
        valid_sample_groups_from_user = list(valid_sample_user.profile["access_information"]["ldap"]["values"])

        query = execute.sql_alchemy_select(
            r.engine(), "access_information.ldap", valid_sample_groups_from_user[0], "contains"
        )
