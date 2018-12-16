import cis_profile
import json
from cis_processor import profile
from cis_processor.common import get_config
from cis_identity_vault.models import user


from logging import getLogger

logger = getLogger(__name__)


class BaseProcessor(object):
    """Object to the basics to check the schema and integrate to dynamodb."""
    def __init__(self, event_record, dynamodb_client, dynamodb_table):
        self.event_record = event_record
        self.dynamodb_client = dynamodb_client
        self.dynamodb_table = dynamodb_table
        self.config = get_config()

    def _load_profiles(self):
        profile_delegate = profile.ProfileDelegate(
            self.event_record, self.dynamodb_client, self.dynamodb_table
        )
        self.profiles = profile_delegate.profiles

    def _profile_to_vault_structure(self, user_profile):
        return {
            'sequence_number': self.event_record['kinesis']['sequenceNumber'],
            'primary_email': user_profile['primary_email']['value'],
            'profile': json.dumps(user_profile),
            'id': user_profile['user_id']['value']
        }

    def process(self):
        self._load_profiles()
        publishers_valid = False
        signatures_valid = False

        if self.needs_integration(self.profiles['new_profile'], self.profiles['old_profile']):
            # Check the rules
            self.profiles['new_profile'].validate()
            publishers_valid = self.profiles['new_profile'].verify_all_publishers(
                previous_user=self.profiles['old_profile']
            )

            if self.config('processor_verify_signatures', namespace='cis', default='True') == 'True':
                logger.info('Testing signatures for user: {}'.format(
                    self.profiles['new_profile'].as_dict()['user_id']['value'])
                )
                signatures_valid = self.profiles['new_profile'].verify_all_signatures()
                logger.info('The result of signature checking for user: {} resulted in: {}'.format(
                        self.profiles['new_profile'].as_dict()['user_id']['value'],
                        signatures_valid
                    )
                )
            else:
                logger.info('Signature checking is currently disabled.  Skipping all signature checks.')
                signatures_valid = True
        else:
            return True

        if signatures_valid is True and publishers_valid is True:
            vault_data_structure = self._profile_to_vault_structure(self.profiles['new_profile'].as_dict())
            identity_vault = user.Profile(self.dynamodb_table)
            logger.info('Tests pass for the integration.  Proceeding to flush to dynamodb for user: {}'.format(
                    self.profiles['new_profile'].as_dict()['user_id']['value']
                )
            )
            identity_vault.create(vault_data_structure)
            return True
        else:
            return False

    def needs_integration(self, new_user_profile, old_user_profile):
        """Retreive the profile from the dynamodb table.  Integrate it as needed."""
        if old_user_profile is not None:
            old_user_profile_dict = old_user_profile.as_dict()
            new_user_profile_dict = new_user_profile.as_dict()
            for key in new_user_profile_dict:
                if new_user_profile_dict[key] != old_user_profile_dict[key]:
                    return True
        else:
            return True
        return False

    def event_type(self):
        """Return kinesis or dynamodb based on event structure."""
        if self.event.get('kinesis') is not None:
            return 'kinesis'

        if self.event.get('dynamodb') is not None:
            return 'dynamodb'
