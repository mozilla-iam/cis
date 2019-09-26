"""Profile exchange takes an event from the dynamodb stream and stores in in postgresql."""
import json
from jsonschema.exceptions import ValidationError
from logging import getLogger
from os import getenv

from cis_profile import profile
from cis_aws import connect
from cis_identity_vault.models import user


logger = getLogger(__name__)


class ProfileBase(object):
    """Expected behaviors for interacting with cis_profile, schema validator.
    Centralizes initializers for common behavior."""

    def __init__(self, user_structure_json=None):
        self.user_structure_json = user_structure_json
        self.cis_profile = None

    def _load_cis_profile(self):
        if self.cis_profile is None:
            self.cis_profile = profile.User(user_structure_json=self.user_structure_json)

    @property
    def valid(self):
        """[Light validation prior to replicating to postgres in order to ensure no tampering.]

        Returns:
            [boolean] -- [Method returns status of pre-flight checks from the profile lib.]
        """
        self._load_cis_profile()
        try:
            self.cis_profile.validate()
            return True
        except ValidationError:
            return False

    @property
    def profile(self):
        """[Return an instance of our borrowed cis_profile object.]

        Returns:
            [object] -- [cis_profile.User object.]
        """
        self._load_cis_profile()
        return self.cis_profile


class BaseDynamoStream(ProfileBase):
    """Defines basic expected behavior for interaction with the dynamodb stream. Supports batch only."""

    def user_ids_from_stream(self, event):
        user_ids = []
        if event.get("Records") is not None:
            for record in event.get("Records"):
                user_ids.append(record["dynamodb"]["Keys"]["id"]["S"])
        else:
            user_ids = None
        return user_ids

    def profiles(self, user_ids=None):
        aws = connect.AWS()
        aws.session(region_name=getenv("DEFAULT_AWS_REGION", "us-west-2"))
        identity_vault_discovery = aws.identity_vault_client()
        dynamodb_client = identity_vault_discovery["client"]
        dynamodb_table = identity_vault_discovery["table"]
        vault = user.Profile(dynamodb_table, dynamodb_client)
        profiles = []

        if user_ids is None:
            these_profiles = vault.all
            for this_profile in these_profiles:
                profiles.append(json.loads(this_profile["profile"]))
        else:
            for user_id in user_ids:
                # for each user id go and get the profile in full from the identity vault
                this_profile = vault.find_by_id(user_id)["Items"][0]
                # validate it
                self.user_structure_json = json.loads(this_profile["profile"])
                if self.valid:
                    # push it onto the stack
                    profiles.append(self.profile.as_dict())
        return profiles


class NoDynamoStream(BaseDynamoStream):
    """Object to return sample behaviors if there is an error in stream processing."""

    def profiles(self):
        return []


class DynamoStream(BaseDynamoStream):
    """Guaranteed object for processing the event stream.
    Inherits from the base class and triggers the null class if unsuccessful
    XXX TBD
    """

    pass


class BasePostgresqlMapper(ProfileBase):
    """Defines the basic behavior for interaction with postgres.
    Maps profiles retreived using the dynamodb layer to the appropriate format.
    Stores the profiles in the relational store as valid structured JSON.
    Supports batch only interaction.
    """

    def to_postgres(self, profiles):
        rds_vault = user.ProfileRDS()
        results = []
        for _ in profiles:
            results.append(rds_vault.find_or_create(_))
        logger.info(f'{len(results)} profiles have been written to the postgresql identity vault.')
        return results


class NoPostgresqlMapper(BasePostgresqlMapper):
    """Fall through class for cases where user profiles fail to process.
    Null class should also dead letter.

    XXX TBD
    """

    pass


class PostgresqlMapper(BasePostgresqlMapper):
    """Guaranteed data mapper and writer class for interaction with postgresql.
    Returns null objects if the operation fails.

    XXX TBD
    """

    pass
