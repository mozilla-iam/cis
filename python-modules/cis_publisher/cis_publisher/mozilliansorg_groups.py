import cis_profile
import cis_publisher
from cis_publisher.publisher import PublisherError
import logging
import json
from queue import Queue
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)
MO_PREFIX = "mozilliansorg_"


def get_nested(d, *keys, default=None):
    if d is None:
        return default
    for key in keys:
        try:
            d = d[key]
        except KeyError:
            return default
    return d


def unpack_string_list(lst=[]):
    try:
        return [el["S"][len(MO_PREFIX) :] for el in lst if el["S"].startswith(MO_PREFIX)]
    except (KeyError, TypeError):
        logger.error("invalid string list {}".format(lst))
        return None


class MozilliansorgGroupUpdate:
    def __init__(self, typ, user_id, groups=[]):
        self.typ = typ
        self.user_id = user_id
        self.groups = groups

    @staticmethod
    def from_record(record):
        """
        Constructs a MozilliansGroupUpdate from a raw sqs record.

        @record: a raw record from an SQS event
        @return: MozilliansGroupUpdate or None to error gracefully.
        """
        body = get_nested(record, "body")
        if not body:
            logger.error("Event without body: {}".format(record))
            return None
        try:
            body = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in body: {}".format(e))
            return None
        user_id = get_nested(body, "dynamodb", "Keys", "user_id", "S")
        new_image = get_nested(body, "dynamodb", "NewImage")
        typ = get_nested(body, "eventName")
        payload_user_id = get_nested(new_image, "user_id", "S")
        if user_id != payload_user_id:
            logger.error("mismatching user_ids {} {}".format(user_id, payload_user_id))
            return None
        groups = unpack_string_list(get_nested(new_image, "groups", "L", default=[]))
        if user_id and typ and groups is not None:
            return MozilliansorgGroupUpdate(typ, user_id, groups)
        return None


class MozilliansorgGroupsPublisher:
    def __init__(self):
        self.secret_manager = cis_publisher.secret.Manager()
        self.publisher = cis_publisher.Publish([], login_method=None, publisher_name="mozilliansorg")

    def publish(self, event):
        """
        Publish all resulting mozilliansorg group updates to CIS resulting from an event.

        @event: raw event from SQS
        """
        # Contruct MozillansGroupUpdates from all records of the event.
        updates = [update for update in map(MozilliansorgGroupUpdate.from_record, event.get("Records", [])) if update]
        # Create partial profile updates for all MozillansGroupUpdates and filter out no-ops.
        update_profiles = [update_profile for update_profile in map(self._prepare_update, updates) if update_profile]
        failed_updates = Queue()
        for update_profile in update_profiles:
            user_id = update_profile.user_id.value
            qs = "/v2/user?user_id={}".format(quote_plus(user_id))
            self.publisher._really_post_with_qs(user_id, qs, update_profile, failed_updates)
        while not failed_updates.empty():
            logger.warn("failed to update: {}".format(failed_updates.get()))
            failed_updates.task_done()

    def _prepare_update(self, update):
        """
        Construct a partial profile for a given update.

        @update: instance of MozilliansGroupUpdates
        @return: a profile with user_id, active and the according updated and signed mozilliansorg access information or
                 None for a no-op.
        """
        if update.groups is None:
            logger.info("No change in mozilliangsorg access information. Skipping.")
            return None
        current_profile = None
        try:
            current_profile = self.publisher.get_cis_user(update.user_id)
        except PublisherError:
            logger.info("No profile for {}, skipping!".format(update.user_id))
            return None
        if not hasattr(current_profile, "user_id"):
            logger.info("No profile for {}, skipping!".format(update.user_id))
            return None

        logger.info("received profile for {}".format(current_profile.user_id.value))
        update_profile = cis_profile.profile.User()
        update_profile.user_id = current_profile.user_id
        update_profile.active = current_profile.active
        updated_groups = self._update_groups(current_profile.access_information.mozilliansorg["values"], update.groups)
        if updated_groups == current_profile.access_information.mozilliansorg["values"]:
            logger.info("No change in mozilliangsorg access information. Skipping.")
            return None
        update_profile.access_information.mozilliansorg["values"] = updated_groups
        if not update_profile.access_information.mozilliansorg.metadata.display:
            update_profile.access_information.mozilliansorg.metadata.display = "ndaed"
        update_profile.update_timestamp("access_information.mozilliansorg")
        try:
            update_profile.sign_attribute("access_information.mozilliansorg", "mozilliansorg")
        except Exception as e:
            logger.critical("Profile data signing failed for user {}: {}".format(update.user_id, e))
            return None

        logger.info("Merged groups for user {}".format(update.user_id))
        return update_profile

    @staticmethod
    def _update_groups(current_groups, mozillians_groups_update):
        """
        Update current gropus based on a mozillians groups update. PMO groups (value == "") overwrite mozillians groups.

        @current_groups: current groups dict from profile v2
        @mozillians_gropus_update: list of mozillians groups
        @return: new groups dict
        """
        updated = {group: None for group in mozillians_groups_update}
        if not current_groups:
            return updated
        pmo_groups = {name: meta for name, meta in current_groups.items() if meta is not None}

        updated.update(pmo_groups)

        return updated
