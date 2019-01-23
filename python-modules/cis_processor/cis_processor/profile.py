"""Unifies old and new profile layers."""
import base64
import json
from cis_identity_vault.models.user import Profile as DynamoDbUser
from cis_profile.profile import User
from logging import getLogger

logger = getLogger(__name__)


class ProfileDelegate(object):
    def __init__(self, event_record, dynamodb_client, dynamodb_table):
        self.event_record = event_record
        self.dynamodb_client = dynamodb_client
        self.dynamodb_table = dynamodb_table

    @property
    def profiles(self):
        return dict(old_profile=self.load_old_user_profile(), new_profile=self.load_new_user_profile())

    def _get_user_id_from_stream(self):
        kinesis_data = self.event_record["kinesis"]["data"]
        user_profile = json.loads(base64.b64decode(kinesis_data))
        profile_v2_data = user_profile
        return profile_v2_data["user_id"]["value"]

    def load_old_user_profile(self):
        user_id = self._get_user_id_from_stream()
        vault_user = DynamoDbUser(self.dynamodb_table)
        search_result = vault_user.find_by_id(user_id)
        if len(search_result.get("Items")) > 0:
            profile_data = search_result.get("Items")[0]
            user_object = User(user_structure_json=json.loads(profile_data["profile"]))
            logger.info("A prior integration has been found for user: {}".format(user_id))
            return user_object
        else:
            logger.info("No user_id was matched for user: {}".format(user_id))
            # Return an empty cis_profile.user.User()
            return User()

    def load_new_user_profile(self):
        """Return an instance of cis_profile User."""
        kinesis_data = self.event_record["kinesis"]["data"]
        user_profile = json.loads(base64.b64decode(kinesis_data))
        profile_v2_data = user_profile
        user_object = User(user_structure_json=profile_v2_data)
        return user_object
