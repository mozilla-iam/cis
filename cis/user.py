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
        self.profile_data = profile_data
        self.dynamodb_table = None

    @property
    def exists(self):
        if self._retrieve_from_vault() is not None:
            return True
        else:
            return False

    def _retrieve_from_vault(self):

        """
        Check if a user exist in dynamodb

        :user: User's id
        """

        if self.dynamodb_table is None:
            self._connect_dynamo_db()

        user_key = {'user_id': self.profile_data.get('user_id')}

        try:
            response = table.get_item(Key=user_key)
            self.profile_data = response
        except Exception:
            logger.exception('DynamoDB GET failed')
            return None

        return response

    def _store_in_vault(self):
        # Put data to DynamoDB
        try:
            response = self.dyanmodb_table.put_item(
                Item=self.profile_data
            )
        except Exception:
            logger.exception('DynamoDB PUT failed')
            return None

        return response

    def _connect_dynamo_db(self):
        """New up a dynamodb resource from boto session."""
        config = get_config()
        dynamodb = self.boto_session.resource('dynamodb')
        dynamodb_table = config('dynamodb_table', namespace='cis')
        self.dynamodb_table = dynamodb.Table(dynamodb_table)