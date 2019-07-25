"""Create, destroy, and configure the appropriate vault for the environment."""
import boto3
import time
from botocore.exceptions import ClientError
from botocore.stub import Stubber
from cis_identity_vault import autoscale
from cis_identity_vault.common import get_config
from cis_identity_vault.models import rds
from logging import getLogger
from sqlalchemy import create_engine


logger = getLogger(__name__)


class IdentityVault(object):
    def __init__(self):
        self.boto_session = None
        self.dynamodb_client = None
        self.config = get_config()

    def connect(self):
        self._session()
        if self.dynamodb_client is None:
            if self._get_cis_environment() == "local":
                dynalite_port = self.config("dynalite_port", namespace="cis", default="4567")
                dynalite_host = self.config("dynalite_host", namespace="cis", default="localhost")
                self.dynamodb_client = self.boto_session.client(
                    "dynamodb", endpoint_url="http://{}:{}".format(dynalite_host, dynalite_port)
                )
            else:
                self.dynamodb_client = self.boto_session.client("dynamodb")
        return self.dynamodb_client

    def _session(self):
        if self.boto_session is None:
            region = self.config("region_name", namespace="cis", default="us-west-2")
            if self._get_cis_environment() == "local":
                self.boto_session = Stubber(boto3.session.Session(region_name=region)).client
            else:
                self.boto_session = boto3.session.Session(region_name=region)
            return self.boto_session

    def _get_cis_environment(self):
        return self.config("environment", namespace="cis", default="local")

    def _generate_table_name(self):
        return "{}-identity-vault".format(self._get_cis_environment())

    def enable_stream(self):
        self.connect()
        result = self.dynamodb_client.update_table(
            TableName=self._generate_table_name(),
            StreamSpecification={"StreamEnabled": True, "StreamViewType": "NEW_AND_OLD_IMAGES"},
        )
        return result

    def enable_autoscaler(self):
        scaler_config = autoscale.ScalableTable(self._generate_table_name())
        scaler_config.connect()
        return scaler_config.enable_autoscaler()

    def tag_vault(self):
        self.connect()
        arn = self.find()
        tags = [
            {"Key": "cis_environment", "Value": self._get_cis_environment()},
            {"Key": "application", "Value": "identity-vault"},
        ]
        try:
            return self.dynamodb_client.tag_resource(ResourceArn=arn, Tags=tags)
        except ClientError:
            logger.error("The table does not support tagging.")
        except Exception as e:
            logger.error("The table did not tag for an unknown reason: {}".format(e))

    def find(self):
        self.connect()
        try:
            if self._get_cis_environment() == "local":
                # Assume that the local identity vault is always called local-identity-vault
                return self.dynamodb_client.describe_table(TableName="local-identity-vault")["Table"]["TableArn"]
            else:
                # Assume that we are in AWS and list tables, describe tables, and check tags.
                tables = self.dynamodb_client.list_tables(Limit=100)

                for table in tables.get("TableNames"):
                    table_arn = self.dynamodb_client.describe_table(TableName=table)["Table"]["TableArn"]

                    if table == self._generate_table_name():
                        return table_arn
        except ClientError as exception:
            if exception.response["Error"]["Code"] == "ResourceNotFoundException":
                return None
            else:
                raise

    def create(self):
        if self._get_cis_environment() not in ["production", "development", "testing"]:
            result = self.dynamodb_client.create_table(
                TableName=self._generate_table_name(),
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[
                    # auth0 user_id
                    {"AttributeName": "id", "AttributeType": "S"},
                    # user_uuid formerly dinopark id (uuid is a reserverd keyword in dynamo, hence user_uuid)
                    {"AttributeName": "user_uuid", "AttributeType": "S"},
                    # sequence number for the last integration
                    {"AttributeName": "sequence_number", "AttributeType": "S"},
                    # value of the primary_email attribute
                    {"AttributeName": "primary_email", "AttributeType": "S"},
                    # value of the primary_username attribute
                    {"AttributeName": "primary_username", "AttributeType": "S"},
                ],
                ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "{}-sequence_number".format(self._generate_table_name()),
                        "KeySchema": [{"AttributeName": "sequence_number", "KeyType": "HASH"}],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                    },
                    {
                        "IndexName": "{}-primary_username".format(self._generate_table_name()),
                        "KeySchema": [
                            {"AttributeName": "primary_username", "KeyType": "HASH"},
                            {"AttributeName": "id", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                    },
                    {
                        "IndexName": "{}-primary_email".format(self._generate_table_name()),
                        "KeySchema": [
                            {"AttributeName": "primary_email", "KeyType": "HASH"},
                            {"AttributeName": "id", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                    },
                    {
                        "IndexName": "{}-user_uuid".format(self._generate_table_name()),
                        "KeySchema": [
                            {"AttributeName": "user_uuid", "KeyType": "HASH"},
                            {"AttributeName": "id", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        # Removed due to moving to pay per query.
                        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                    },
                ],
            )
        else:
            result = self.dynamodb_client.create_table(
                TableName=self._generate_table_name(),
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[
                    # auth0 user_id
                    {"AttributeName": "id", "AttributeType": "S"},
                    # user_uuid formerly dinopark id (uuid is a reserverd keyword in dynamo, hence user_uuid)
                    {"AttributeName": "user_uuid", "AttributeType": "S"},
                    # sequence number for the last integration
                    {"AttributeName": "sequence_number", "AttributeType": "S"},
                    # value of the primary_email attribute
                    {"AttributeName": "primary_email", "AttributeType": "S"},
                    # value of the primary_username attribute
                    {"AttributeName": "primary_username", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "{}-sequence_number".format(self._generate_table_name()),
                        "KeySchema": [{"AttributeName": "sequence_number", "KeyType": "HASH"}],
                        "Projection": {"ProjectionType": "ALL"},
                    },
                    {
                        "IndexName": "{}-primary_username".format(self._generate_table_name()),
                        "KeySchema": [
                            {"AttributeName": "primary_username", "KeyType": "HASH"},
                            {"AttributeName": "id", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                    },
                    {
                        "IndexName": "{}-primary_email".format(self._generate_table_name()),
                        "KeySchema": [
                            {"AttributeName": "primary_email", "KeyType": "HASH"},
                            {"AttributeName": "id", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                    },
                    {
                        "IndexName": "{}-user_uuid".format(self._generate_table_name()),
                        "KeySchema": [
                            {"AttributeName": "user_uuid", "KeyType": "HASH"},
                            {"AttributeName": "id", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                    },
                ],
            )
        waiter = self.dynamodb_client.get_waiter("table_exists")

        if self._get_cis_environment() in ["production", "development", "testing"]:
            waiter.wait(TableName=self._generate_table_name(), WaiterConfig={"Delay": 20, "MaxAttempts": 20})
            self.tag_vault()
            self.setup_stream()
        else:
            waiter.wait(TableName=self._generate_table_name(), WaiterConfig={"Delay": 1, "MaxAttempts": 5})

        return result

    def destroy(self):
        result = self.dynamodb_client.delete_table(TableName=self._generate_table_name())
        return result

    def __get_table_resource(self):
        region = self.config("region_name", namespace="cis", default="us-west-2")
        if self._get_cis_environment() == "local":
            self.boto_session = Stubber(boto3.session.Session(region_name=region)).client
            dynalite_port = self.config("dynalite_port", namespace="cis", default="4567")
            dynalite_host = self.config("dynalite_host", namespace="cis", default="localhost")

            dynamodb_resource = self.boto_session.resource(
                "dynamodb", endpoint_url="http://{}:{}".format(dynalite_host, dynalite_port)
            )
            table = dynamodb_resource.Table(self._generate_table_name())
        else:
            dynamodb_resource = boto3.resource("dynamodb", region_name=region)
            table = dynamodb_resource.Table(self._generate_table_name())
        return table

    def find_or_create(self):
        if self.find() is not None:
            table = self.__get_table_resource()
        else:
            self.create()
            table = self.__get_table_resource()
        return table

    def describe_indices(self):
        return self.dynamodb_client.describe_table(TableName=self._generate_table_name())

    def _has_stream(self):
        result = self.dynamodb_client.describe_table(TableName=self._generate_table_name()).get("Table")

        if result.get("StreamSpecification"):
            return True
        else:
            return False

    def setup_stream(self):
        if self._has_stream() is False:
            try:
                return self.dynamodb_client.update_table(
                    TableName=self._generate_table_name(),
                    StreamSpecification={"StreamEnabled": True, "StreamViewType": "KEYS_ONLY"},
                )
            except ClientError as e:
                logger.error("The table does not support streams: {}.".format(e))
                return
            except Exception as e:
                logger.error("The table did not tag for an unknown reason: {}".format(e))


class RelationalIdentityVault(object):
    """Create a postgres model of the data that is in DynamoDb in order to support advanced search."""

    def __init__(self):
        self.config = get_config()
        self.environment = self.config("environment", namespace="cis", default="testing")
        self.postgres_host = self.config("postgres_host", namespace="cis", default="localhost")
        self.postgres_port = int(self.config("postgres_port", namespace="cis", default="5432"))
        self.db_name = self.config("identity_vault", namespace="cis", default=f"{self.environment}-identity-vault")
        self.db_user = self.config("db_user", namespace="cis", default="cis_user")
        self.db_password = self._db_password_from_ssm()

    def _db_password_from_ssm(self):
        password_from_environment = self.config("db_password", namespace="cis", default="None")
        retries = 5
        backoff = 15
        if password_from_environment != "None":
            return password_from_environment
        else:
            result = None
            while result is None:
                try:
                    self.ssm_client = boto3.client("ssm")
                    ssm_path = self.config("db_password_path", namespace="cis", default="/iam/development")
                    ssm_response = self.ssm_client.get_parameter(Name=ssm_path, WithDecryption=True)
                    result = ssm_response.get("Parameter").get("Value")
                    logger.debug("Secret manager SSM provider loading db_password: {}".format(ssm_path))
                except ClientError as e:
                    retries = retries - 1
                    backoff = backoff + 1
                    logger.debug(
                        "Backing-off: fetch secret due to: {} retries {} backoff {}".format(e, retries, backoff)
                    )
                    time.sleep(backoff)
                if retries <= 0:
                    break
                else:
                    pass
            return result

    def _db_string(self):
        proto = "postgresql+psycopg2://"
        access_information = f"{self.db_user}:{self.db_password}"
        connection_information = f"@{self.postgres_host}:{self.postgres_port}/{self.db_name}"
        return proto + access_information + connection_information

    def engine(self):
        db = create_engine(self._db_string())
        engine = db.connect()
        return engine

    def create(self):
        return rds.Base.metadata.create_all(self.engine())

    def delete(self):
        return rds.Base.metadata.drop_all(self.engine())

    def table(self):
        metadata = rds.Base.metadata
        metadata.bind = self.engine()
        return metadata.tables.get("people")
