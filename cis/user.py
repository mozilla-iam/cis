"""First class object to represent a user and data about that user."""
import logging

from cis.settings import get_config


logger = logging.getLogger(__name__)


class Profile(object):
    def __init__(self, boto_session=None, profile_data=None):
        """
        :param boto_session: The boto session object from the constructor.
        :param profile_data: The decrypted user profile JSON.
        """
        self.boto_session = boto_session
        self.config = get_config()
        self.profile_data = profile_data
        self.dynamodb_table = None

    @property
    def exists(self):
        if self._retrieve_from_vault() is not None:
            return True
        else:
            return False

    def retrieve_from_vault(self):
        logger.info(
            'Attempting to retrieve the following from the vault: {}'.format(
                self.profile_data.get('user_id')
            )
        )

        if not self.dynamodb_table:
            self._connect_dynamo_db()

        user_key = {'user_id': self.profile_data.get('user_id')}
        response = self.dynamodb_table.get_item(Key=user_key)
        self.profile_data = response

        return response

    def store_in_vault(self):
        logger.info(
            'Attempting storage of the following user to the vault: {}'.format(
                self.profile_data.get('user_id')
            )
        )

        if not self.dynamodb_table:
            self._connect_dynamo_db()

        response = self.dynamodb_table.put_item(
            Item=self.profile_data
        )

        return (response['ResponseMetadata']['HTTPStatusCode'] is 200)

    def _connect_dynamo_db(self):
        """New up a dynamodb resource from boto session."""
        dynamodb = self.boto_session.resource('dynamodb')
        dynamodb_table = self.config('dynamodb_table', namespace='cis')
        self.dynamodb_table = dynamodb.Table(dynamodb_table)
