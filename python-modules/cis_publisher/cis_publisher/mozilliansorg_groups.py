import cis_profile
import cis_publisher
import logging
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

    def from_record(record):
        user_id = get_nested(record, "body", "dynamodb", "Keys", "user_id", "S")
        new_image = get_nested(record, "body", "dynamodb", "NewImage")
        typ = get_nested(record, "body", "eventName")
        payload_user_id = get_nested(new_image, "user_id", "S")
        if user_id != payload_user_id:
            logger.error("missmatching user_ids {} {}".format(user_id, payload_user_id))
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
        updates = [update for update in map(MozilliansorgGroupUpdate.from_record, event.get("Records", [])) if update]
        update_profiles = [update_profile for update_profile in map(self._prepare_update, updates) if update_profile]
        failed_updates = Queue()
        for update_profile in update_profiles:
            user_id = update_profile.user_id.value
            qs = "/v2/user/?user_id={}".format(quote_plus(user_id))
            self.publisher._really_post_with_qs(user_id, qs, update_profile, failed_updates)
        while not failed_updates.empty():
            logger.warn("failed to update: {}".format(failed_updates.get()))
            failed_updates.task_done()

    def _prepare_update(self, update):
        current_profile = self.publisher.get_cis_user(update.user_id)
        update_profile = cis_profile.profile.User()
        update_profile.user_id = current_profile.user_id
        update_profile.active = current_profile.active
        update_profile.access_information.mozilliansorg.values = {group: None for group in update.groups}
        if not update_profile.access_information.mozilliansorg.metadata.display:
            update_profile.access_information.mozilliansorg.metadata.display = "private"
        update_profile.update_timestamp("access_information.mozilliansorg")
        try:
            update_profile.sign_attribute("access_information.mozilliansorg", "mozilliansorg")
        except Exception as e:
            logger.critical("Profile data signing failed for user {}: {}".format(update.user_id, e))
            return None
        return update_profile
