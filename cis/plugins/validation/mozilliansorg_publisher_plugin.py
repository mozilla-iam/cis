import logging

from cis.libs import utils

utils.StructuredLogger(name=__name__, level=logging.INFO)
logger = logging.getLogger(__name__)

# Allows user creation by this publisher.
CAN_CREATE_USER = True  # XXX TBD turn this back to false when there is another method of user provision.
ENFORCE_ATTR_WHITELIST = False


def run(publisher, vault_json, profile_json):
    """
    Check if a user mozillian's profile properly namespaces mozillians groups
    and whitelists which fields mozillians.org has authority over.

    :publisher: The CIS publisher
    :user: The user from the CIS vault
    :profile_json: The user profile passed by the publisher
    """

    # This plugin only cares about mozillians.org publisher
    if publisher != 'mozilliansorg':
        return True

    # Validate only whitelisted fields for this publisher are in use
    whitelist = [
        'timezone',
        'displayName',
        'firstName',
        'lastName',
        'preferredLanguage',
        'primaryEmail',
        'emails',
        'phoneNumbers',
        'uris',
        'nicknames',
        'SSHFingerprints',
        'PGPFingerprints',
        'picture',
        'shirtSize',
        'groups',
        'tags'
    ]

    # Validate that only whitelisted accounts/profiles issued from vetted IdPs (generally, the ones enforcing MFA)
    # can get groups assigned as these are used for access control
    whitelist_idp_with_enforced_mfa = [
        'github|',  # GitHub has a rule in Auth0 to enforce MFA
        'ad|'       # = LDAP which enforces Duo MFA in Auth0
    ]

    # Check the easiest case. None type.
    if vault_json is None and CAN_CREATE_USER is False:
        logger.exception('permission denied: publisher {} attempted to modify user that does not exist'
                         ' in the identity vault'.format(publisher))
        return False

    # Attr whitelist is currently disabled as mozilliansorg needs to be able to create new Profiles
    # XXX TBD This should pull back a profile from person api for this comparison
    if ENFORCE_ATTR_WHITELIST is True:
        for attr in vault_json:
            if attr not in whitelist:
                if profile_json.get(attr) != vault_json.get(attr):
                    logger.exception('permission denied: publisher {} attempted to modify user attributes it has no'
                                     'authority over'.format(publisher))
                    return False

    # Validate namespaced groups only come from Mozillians.org
    # This is the whitelisted group prefix for this publisher:
    # group sub structure looks like: user.groups = [ 'group_from_ldap1', 'moziliansorg_mytestgroup', ...]
    prefix = 'mozilliansorg_'

    old_groups = vault_json.get('groups', [])
    new_groups = profile_json.get('groups', [])

    for profile_idp in whitelist_idp_with_enforced_mfa:
        if not profile_json.get('user_id').startswith(profile_idp):
            if new_groups:
                logger.exception('permission denied: publisher {} attempted to set `groups` attribute values for '
                                 'a user profile initiated by an IdP that is not allowed to use '
                                 '`groups`'.format(publisher))
                return False

    # Check is we have any non-mozilliansorg group that has been *removed*
    for g in old_groups:
        if not g.startswith(prefix):
            if g not in new_groups:
                logger.exception('permission denied: publisher {} attempted to remove groups it has no authority over'
                                 .format(publisher))
                return False

    # Check is we have any non-mozilliansorg group that has been *added*
    for g in new_groups:
        if not g.startswith(prefix):
            if g not in old_groups:
                logger.exception('permission denied: publisher {} attempted to add groups it has no authority over'
                                 .format(publisher))
                return False

    return True
