"""Governs crud operations for profiles in the identity vault.
user_profile must be passed to this in the form required by dynamodb
{
    'id': 'ad|foo',
    'uuid': 'dc8cbad4-4426-406f-998e-9d95edb06bdc',
    'primary_email': 'foo@xyz.com',
    'sequence_number': '123456',
    'primary_email': 'foomcbar',
    'profile': 'jsondumpofuserfullprofile'
}
"""
import json
import logging
import uuid
import urllib.parse
from boto3.dynamodb.conditions import Attr
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError
from botocore.exceptions import ParamValidationError
from traceback import format_exc

from cis_profile import User

# Import depends for interaction with the postgres database
from cis_identity_vault.models import rds
from cis_identity_vault import vault
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound

from cis_identity_vault.parallel_dynamo import scan


logger = logging.getLogger(__name__)


class Profile(object):
    def __init__(self, dynamodb_table_resource=None, dynamodb_client=None, transactions=True):
        """Take a dynamodb table resource to use for operations."""
        self.table = dynamodb_table_resource
        self.client = dynamodb_client
        self.transactions = transactions
        self.deserializer = TypeDeserializer()

    def _run_transaction(self, transact_items):
        sequence_numbers = []
        for t in transact_items:
            if "Update" in t:
                sequence_numbers.append(t["Update"]["ExpressionAttributeValues"][":sn"]["S"])
            else:
                sequence_numbers.append(t["Put"]["Item"]["sequence_number"]["S"])

        try:
            self.client.transact_write_items(
                TransactItems=transact_items, ReturnConsumedCapacity="TOTAL", ReturnItemCollectionMetrics="SIZE"
            )
        except ClientError as e:
            logger.warning("Transaction failed", extra={"reason": e, "trace": format_exc()})
            raise ValueError("Transaction failed - profile issue?", e)

        return {"status": "200", "ResponseMetadata": {"HTTPStatusCode": 200}, "sequence_numbers": sequence_numbers}

    def create(self, user_profile):
        if self.transactions:
            res = self._create_with_transaction(user_profile)
        else:
            res = self._create_without_transaction(user_profile)

        if res.get("ResponseMetadata", False):
            status_code = res["ResponseMetadata"]["HTTPStatusCode"]
            sequence_number = user_profile["sequence_number"]

        return {"status": status_code, "sequence_number": sequence_number}

    def _create_without_transaction(self, user_profile):
        if user_profile["sequence_number"] is None:
            user_profile["sequence_number"] = str(uuid.uuid4().int)

        cis_profile_user_object = User(user_structure_json=json.loads(user_profile["profile"]))

        return self.table.put_item(
            Item={
                "id": user_profile["id"],
                "user_uuid": user_profile["user_uuid"],
                "profile": user_profile["profile"],
                "primary_email": user_profile["primary_email"],
                "primary_username": user_profile["primary_username"],
                "sequence_number": user_profile["sequence_number"],
                "active": bool(json.loads(user_profile["profile"])["active"]["value"]),
                "flat_profile": {
                    k: self.deserializer.deserialize(v)
                    for k, v in cis_profile_user_object.as_dynamo_flat_dict().items()
                },
            }
        )

    def _create_with_transaction(self, user_profile):
        if user_profile["sequence_number"] is None:
            user_profile["sequence_number"] = str(uuid.uuid4().int)

        cis_profile_user_object = User(user_structure_json=json.loads(user_profile["profile"]))

        transact_items = {
            "Put": {
                "Item": {
                    "id": {"S": user_profile["id"]},
                    "user_uuid": {"S": user_profile["user_uuid"]},
                    "profile": {"S": user_profile["profile"]},
                    "primary_email": {"S": user_profile["primary_email"]},
                    "primary_username": {"S": user_profile["primary_username"]},
                    "sequence_number": {"S": user_profile["sequence_number"]},
                    "active": {"BOOL": json.loads(user_profile["profile"])["active"]["value"]},
                    "flat_profile": {"M": cis_profile_user_object.as_dynamo_flat_dict()},
                },
                "ConditionExpression": "attribute_not_exists(id)",
                "TableName": self.table.name,
                "ReturnValuesOnConditionCheckFailure": "NONE",
            }
        }
        return self._run_transaction([transact_items])

    def update(self, user_profile):
        if self.transactions:
            res = self._update_with_transaction(user_profile)
        else:
            res = self._update_without_transaction(user_profile)
        return res

    def _update_with_transaction(self, user_profile):
        cis_profile_user_object = User(user_structure_json=json.loads(user_profile["profile"]))
        transact_items = {
            "Update": {
                "Key": {"id": {"S": user_profile["id"]}},
                "ExpressionAttributeValues": {
                    ":p": {"S": user_profile["profile"]},
                    ":u": {"S": user_profile["user_uuid"]},
                    ":pe": {"S": user_profile["primary_email"]},
                    ":pn": {"S": user_profile["primary_username"]},
                    ":sn": {"S": user_profile["sequence_number"]},
                    ":a": {"BOOL": json.loads(user_profile["profile"])["active"]["value"]},
                    ":fp": {"M": cis_profile_user_object.as_dynamo_flat_dict()},
                },
                "ConditionExpression": "attribute_exists(id)",
                "UpdateExpression": "SET profile = :p, primary_email = :pe, sequence_number = :sn, user_uuid = :u,"
                "primary_username = :pn, active = :a, flat_profile = :fp",
                "TableName": self.table.name,
                "ReturnValuesOnConditionCheckFailure": "NONE",
            }
        }
        return self._run_transaction([transact_items])

    def _update_without_transaction(self, user_profile):
        cis_profile_user_object = User(user_structure_json=json.loads(user_profile["profile"]))

        return self.table.put_item(
            Item={
                "id": user_profile["id"],
                "user_uuid": user_profile["user_uuid"],
                "profile": user_profile["profile"],
                "primary_email": user_profile["primary_email"],
                "primary_username": user_profile["primary_username"],
                "sequence_number": user_profile["sequence_number"],
                "active": bool(json.loads(user_profile["profile"])["active"]["value"]),
                "flat_profile": {
                    k: self.deserializer.deserialize(v)
                    for k, v in cis_profile_user_object.as_dynamo_flat_dict().items()
                },
            }
        )

    def delete(self, user_profile):
        res = self._delete_without_transaction(user_profile)
        return res

    def _delete_without_transaction(self, user_profile):
        return self.table.delete_item(Key={"id": user_profile["id"]})

    def create_batch(self, list_of_profiles):
        sequence_numbers = []
        for profile in list_of_profiles:
            sequence_numbers.append(profile["sequence_number"])
        if self.transactions:
            res = self._create_items_with_transaction(list_of_profiles)

            if res.get("ResponseMetadata", False):
                status_code = res["ResponseMetadata"]["HTTPStatusCode"]

            return {"status": status_code, "sequence_numbers": sequence_numbers}
        else:
            try:
                res = self._put_items_without_transaction(list_of_profiles)
                return {"status": "200", "sequence_numbers": sequence_numbers}
            except Exception as e:
                logger.error("Could not write batch due to: {}".format(e))
                return {"status": "500", "sequence_numbers": sequence_numbers}

    def _put_items_without_transaction(self, list_of_profiles):
        sequence_numbers = []
        with self.table.batch_writer() as batch:
            for profile in list_of_profiles:
                cis_profile_user_object = User(user_structure_json=json.loads(profile["profile"]))

                batch.put_item(
                    Item={
                        "id": profile["id"],
                        "user_uuid": profile["user_uuid"],
                        "profile": profile["profile"],
                        "primary_email": profile["primary_email"],
                        "primary_username": profile["primary_username"],
                        "sequence_number": profile["sequence_number"],
                        "active": bool(json.loads(profile["profile"])["active"]["value"]),
                        "flat_profile": {
                            k: self.deserializer.deserialize(v)
                            for k, v in cis_profile_user_object.as_dynamo_flat_dict().items()
                        },
                    }
                )
                sequence_numbers.append(profile["sequence_number"])

        return {"status": "200", "ResponseMetadata": {"HTTPStatusCode": 200}, "sequence_numbers": sequence_numbers}

    def _create_items_with_transaction(self, list_of_profiles):
        transact_items = []
        for user_profile in list_of_profiles:
            if user_profile["sequence_number"] is None:
                user_profile["sequence_number"] = str(uuid.uuid4().int)

            # XXX TBD cover this with tests.  Currently dynalite does not support tests for transactions.
            cis_profile_user_object = User(user_structure_json=json.loads(user_profile["profile"]))
            transact_item = {
                "Put": {
                    "Item": {
                        "id": {"S": user_profile["id"]},
                        "user_uuid": {"S": user_profile["user_uuid"]},
                        "profile": {"S": user_profile["profile"]},
                        "primary_email": {"S": user_profile["primary_email"]},
                        "primary_username": {"S": user_profile["primary_username"]},
                        "sequence_number": {"S": user_profile["sequence_number"]},
                        "active": {"BOOL": json.loads(user_profile["profile"])["active"]["value"]},
                        "flat_profile": {"M": cis_profile_user_object.as_dynamo_flat_dict()},
                    },
                    "ConditionExpression": "attribute_not_exists(id)",
                    "TableName": self.table.name,
                    "ReturnValuesOnConditionCheckFailure": "NONE",
                }
            }
            transact_items.append(transact_item)
        logger.debug("Attempting to create batch of transactions for: {}".format(transact_items))
        return self._run_transaction(transact_items)

    def update_batch(self, list_of_profiles):
        if self.transactions:
            res = self._update_batch_with_transaction(list_of_profiles)
        else:
            res = self._put_items_without_transaction(list_of_profiles)
        return res

    def _update_batch_with_transaction(self, list_of_profiles):
        transact_items = []
        for user_profile in list_of_profiles:
            cis_profile_user_object = User(user_structure_json=json.loads(user_profile["profile"]))
            update_expression = "SET profile = :p, primary_email = :pe, \
                sequence_number = :sn, user_uuid = :u, primary_username = :pn, \
                active = :a, flat_profile = :fp"
            transact_item = {
                "Update": {
                    "Key": {"id": {"S": user_profile["id"]}},
                    "ExpressionAttributeValues": {
                        ":p": {"S": user_profile["profile"]},
                        ":u": {"S": user_profile["user_uuid"]},
                        ":pe": {"S": user_profile["primary_email"]},
                        ":pn": {"S": user_profile["primary_username"]},
                        ":sn": {"S": user_profile["sequence_number"]},
                        ":a": {"BOOL": json.loads(user_profile["profile"])["active"]["value"]},
                        ":fp": {"M": cis_profile_user_object.as_dynamo_flat_dict()},
                    },
                    "ConditionExpression": "attribute_exists(id)",
                    "UpdateExpression": update_expression,
                    "TableName": self.table.name,
                    "ReturnValuesOnConditionCheckFailure": "NONE",
                }
            }
            transact_items.append(transact_item)
        logger.debug("Attempting to update batch of transactions for: {}".format(transact_items))
        return self._run_transaction(transact_items)

    def find_by_id(self, id):
        result = self.table.query(KeyConditionExpression=Key("id").eq(id))
        return result

    def find_by_email(self, primary_email):
        result = self.table.query(
            IndexName="{}-primary_email".format(self.table.table_name),
            KeyConditionExpression=Key("primary_email").eq(primary_email),
        )
        return result

    def find_by_uuid(self, uuid):
        result = self.table.query(
            IndexName="{}-user_uuid".format(self.table.table_name), KeyConditionExpression=Key("user_uuid").eq(uuid)
        )
        return result

    def find_by_username(self, primary_username):
        result = self.table.query(
            IndexName="{}-primary_username".format(self.table.table_name),
            KeyConditionExpression=Key("primary_username").eq(primary_username),
        )
        return result

    @property
    def all(self):
        response = self.table.scan()
        users = response.get("Items")
        while "LastEvaluatedKey" in response:
            response = self.table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            users.extend(response["Items"])
        return users

    def all_filtered(self, connection_method=None, active=None, next_page=None):
        """
        @query_filter str login_method
        Returns a dict of all users filtered by query_filter
        """

        projection_expression = "id, primary_email, user_uuid, active"
        next_page = next_page_to_dynamodb(next_page)

        if connection_method:
            logger.debug("No active filter passed.  Assuming we need all users.")
            expression_attr = {":id": {"S": connection_method}}
            filter_expression = "begins_with(id, :id)"

        if connection_method and active is not None:
            logger.debug("Asking for only the users with active state: {}".format(active))
            expression_attr = {":id": {"S": connection_method}, ":a": {"BOOL": active}}
            filter_expression = ":a = active AND begins_with(id, :id) AND attribute_exists(active)"

        response = scan(
            self.client,
            table_name=self.table.name,
            filter_expression=filter_expression,
            expression_attr=expression_attr,
            projection_expression=projection_expression,
            exclusive_start_keys=next_page,
        )
        return dict(users=response["users"], nextPage=last_evaluated_to_friendly(response.get("nextPage")))

    def find_or_create(self, user_profile):
        profilev2 = json.loads(user_profile["profile"])
        if len(self.find_by_id(profilev2["user_id"]["value"])["Items"]) > 0:
            res = self.update(user_profile)
            logger.info("A user profile exists already for: {}".format(profilev2["user_id"]["value"]))
        else:
            res = self.create(user_profile)
            logger.info("A user profile does not exist for: {}".format(profilev2["user_id"]["value"]))
        return res

    def find_or_create_batch(self, user_profiles):
        updates = []
        creations = []
        for user_profile in user_profiles:
            profilev2 = json.loads(user_profile["profile"])
            if len(self.find_by_id(profilev2["user_id"]["value"])["Items"]) > 0:
                logger.debug("Adding profile to the list of updates to perform: {}".format(profilev2))
                updates.append(user_profile)
            else:
                logger.debug("Adding profile to the list of creations to perform: {}".format(profilev2))
                creations.append(user_profile)

        try:
            if len(creations) > 0:
                res_create = self.create_batch(creations)
                logger.debug("There are {} creations to perform in this batch.".format(res_create))
            else:
                res_create = None
        except ClientError as e:
            res_create = None
            logger.error("Could not run batch transaction due to: {}".format(e))
        except ParamValidationError as e:
            res_create = None
            logger.error("Could not run batch transaction due to: {}".format(e))

        try:
            if len(updates) > 0:
                res_update = self.update_batch(updates)
                logger.debug("There are {} updates to perform in this batch.".format(len(updates)))
            else:
                res_update = None
        except ClientError as e:
            res_update = None
            logger.error("Could not run batch transaction due to: {}".format(e))
        except ParamValidationError as e:
            res_update = None
            logger.error("Could not run batch transaction due to: {}".format(e))

        logger.info("Updates were: {}".format(len(updates)))
        logger.info("Creates were: {}".format(len(creations)))

        return [res_create, res_update]

    def all_by_page(self, next_page=None):
        if next_page is not None:
            response = self.table.scan(ExclusiveStartKey=next_page)
        else:
            response = self.table.scan()
        return response

    def _projection_expression_generator(self, full_profiles):
        """Determines what attributes are returned from a scan."""
        if full_profiles:
            projection_expression = "id, profile, active"
        else:
            projection_expression = "id, active"

        return projection_expression

    def _namespace_generator(self, attr, comparator):
        """Where should the comparison in the filter expression search the flat profile."""
        try:
            full_attr = attr.split(".")[1]
        except TypeError as e:
            logger.error(f"Problem splitting path due to: {e}", extra={"error": e})
            full_attr = attr

        if full_attr in ["ldap", "mozilliansorg", "access_provider"]:
            namespace = f"flat_profile.{attr}.{comparator}"
        else:
            namespace = f"flat_profile.{attr}"
        logger.debug("Namespace generated: {}".format(namespace))
        return namespace

    def _filter_expression_generator(self, attr, namespace, comparator, operator, active):
        """Return a filter expression based on the attr to compare to."""
        structures_using_nulls = ["access_information.ldap", "access_information.mozilliansorg"]

        if attr in structures_using_nulls:
            if operator == "eq":
                filter_expression = Attr(namespace).eq(None)
            if operator == "not":
                filter_expression = Attr(namespace).not_exists()
        else:
            if operator == "eq":
                filter_expression = Attr(namespace).eq(comparator)
            if operator == "not":
                filter_expression = Attr(namespace).ne(comparator)

        return filter_expression

    def _result_generator(self, attr, namespace, operator, comparator, full_profiles, last_evaluated_key, active):
        scan_kwargs = dict(
            FilterExpression=self._filter_expression_generator(attr, namespace, comparator, operator, active),
            ProjectionExpression=self._projection_expression_generator(full_profiles),
        )
        if last_evaluated_key is not None:
            scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

        results = self.table.scan(**scan_kwargs)
        return results

    def _attr_to_operator(self, attr):
        """Parse the attribute to determine if this is a not operation."""
        if attr.startswith("not"):
            return "not"
        else:
            return "eq"
        # In future support and operations through better parsing.

    def _remove_op_from_attr(self, attr):
        """Removes condition from attribute."""
        if attr.startswith("not"):
            return attr.split("not_")[1]
        else:
            return attr

    def _results_to_response(self, results, full_profiles, active):
        users = []
        for user in results.get("Items"):
            if user["active"] == active:
                if full_profiles:
                    users.append(
                        dict(id=user["id"], profile=json.loads(user["profile"]))  # JSONify dumped profile struct.
                    )
                else:
                    users.append(dict(id=user["id"]))
            else:
                logger.debug("This user has been filtered by the active query.")
        return users

    def find_by_any(self, attr, comparator, next_page=None, full_profiles=False, active=True):
        """Allow query on any attribute serialized to the flat profile."""
        users = []
        if next_page is not None:
            next_page = {"id": next_page}

        operator = self._attr_to_operator(attr)
        attr = self._remove_op_from_attr(attr)
        namespace = self._namespace_generator(attr, comparator)

        results = self._result_generator(attr, namespace, operator, comparator, full_profiles, next_page, active)

        if results.get("LastEvaluatedKey") is not None:
            next_page = results.get("LastEvaluatedKey")["id"]
        else:
            next_page = None

        users.extend(self._results_to_response(results, full_profiles, active))
        while len(users) < 10 and next_page is not None:
            next_page = {"id": next_page}
            moar_users = self._result_generator(attr, namespace, operator, comparator, full_profiles, next_page, active)
            logger.debug(moar_users)
            if moar_users.get("LastEvaluatedKey") is not None:
                next_page = moar_users.get("LastEvaluatedKey")["id"]
            else:
                next_page = None

            users.extend(self._results_to_response(moar_users, full_profiles, active))
            logger.debug(users)

        logger.debug("At least 10 or all users present in page.  Sending it.")
        return dict(users=users, nextPage=next_page)


class ProfileRDS(object):
    """Manage user profiles writing to the postgres database."""

    def __init__(self):
        self.engine = vault.RelationalIdentityVault().engine()
        Session = sessionmaker()
        self.session = Session(bind=self.engine)
        self.scoped_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=self.engine))
        rds.Base.query = self.scoped_session.query_property()

    def create(self, user_profile):
        if isinstance(user_profile, str):
            user_profile = json.loads(user_profile)

        user = rds.People()
        user.user_id = user_profile["user_id"].get("value")
        user.primary_email = user_profile["primary_email"].get("value")
        user.profile = user_profile
        user.user_uuid = user_profile["uuid"].get("value")
        user.primary_username = user_profile["primary_username"].get("value")
        user.sequence_number = str(uuid.uuid4().int)
        self.scoped_session.add(user)
        self.scoped_session.commit()
        return self.find(user_profile)

    def delete(self, user_profile):
        if isinstance(user_profile, str):
            user_profile = json.loads(user_profile)

        user = self.find(user_profile)
        self.scoped_session.delete(user)
        self.scoped_session.commit()
        return None

    def update(self, user_profile):
        if isinstance(user_profile, str):
            user_profile = json.loads(user_profile)

        user = self.find(user_profile)
        user.user_id = user_profile["user_id"].get("value")
        user.primary_email = user_profile["primary_email"].get("value")
        user.profile = user_profile
        user.user_uuid = user_profile["uuid"].get("value")
        user.primary_username = user_profile["primary_username"].get("value")
        user.sequence_number = str(uuid.uuid4().int)
        self.scoped_session.add(user)
        self.scoped_session.commit()
        return rds.People().query.filter_by(user_id=user.user_id).one()

    def find(self, user_profile):
        if isinstance(user_profile, str):
            user_profile = json.loads(user_profile)
        try:
            user = rds.People().query.filter_by(user_id=user_profile["user_id"].get("value")).one()
        except NoResultFound:
            user = None
        return user

    def find_by_id(self, user_id):
        try:
            user = rds.People().query.filter_by(user_id=user_id).one()
        except NoResultFound:
            user = None
        return user

    def find_by_email(self, primary_email):
        try:
            users = (
                self.session.query(rds.People)
                .filter(rds.People.profile[("primary_email", "value")].astext == primary_email)
                .all()
            )
        except NoResultFound:
            users = []
        return users

    def find_by_uuid(self, uuid):
        try:
            user = self.session.query(rds.People).filter(rds.People.profile[("uuid", "value")].astext == uuid).one()
        except NoResultFound:
            user = None
        return user

    def find_by_username(self, primary_username):
        try:
            user = (
                self.session.query(rds.People)
                .filter(rds.People.profile[("primary_username", "value")].astext == primary_username)
                .one()
            )
        except NoResultFound:
            user = None
        return user

    def find_or_create(self, user_profile):
        if self.find(user_profile) is not None:
            result = self.update(user_profile).user_id
        else:
            result = self.create(user_profile).user_id
        return result


def last_evaluated_to_friendly(last_evaluated_keys):
    """
    Received from Dynamo, and serialized into something our clients can
    understand (or rather, use: this _should_ be an opaque token to
    clients).

    When we're paginating through Dynamo, each segment returns a
    `LastEvaluatedKey`, which we need to specify as `ExclusiveStartKey` in
    subsequent requests. These `ExclusiveStartKey` is segment-specific,
    hence the care here to serialize these in the order returned.

    * `None`, indicating that we've completely finished, there are no more
      results any segment can return;
    * `list[Optional[Any]]`, indicating that _some_ segments have results
      left.

    Our clients' pagination logic (at least as seen by various publishers),
    will consider the query over once we return `None`.
    """
    if not last_evaluated_keys:
        return None
    next_page = []
    for last_evaluated_key in last_evaluated_keys:
        # A signal that the segment is done scanning.
        if last_evaluated_key is None:
            id = ""
        else:
            id = last_evaluated_key["id"]["S"]
        next_page.append(id)
    # If there are at all any segments left with work, then continue.
    if any(next_page):
        next_page_raw = ",".join(next_page)
        return urllib.parse.quote(next_page_raw)
    else:
        return None


def next_page_to_dynamodb(next_page):
    """
    Received from _clients_, and deserialized into something our parallel
    Dynamo code understands.

    A complication here is that we can't reuse `None`, since that would
    cause a segment to start from the beginning. So, we use a sentinel
    value of `""` to signal to the parallel Dynamo code that we should
    skip this segment.

    When Dynamo returns `None`, that means _all_ segments are done. If it
    returns a `list[Optional[Any]]`, that means that we can still make
    progress on some segments.
    """
    if not next_page:
        return None
    next_page_unquoted = urllib.parse.unquote(next_page)
    exclusive_start_keys = []
    for last_evaluated_key in next_page_unquoted.split(","):
        if last_evaluated_key == "":
            id = None
        else:
            id = {"id": {"S": last_evaluated_key}}
        exclusive_start_keys.append(id)
    return exclusive_start_keys
