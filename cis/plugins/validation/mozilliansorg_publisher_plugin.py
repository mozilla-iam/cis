import logging

logger = logging.getLogger(__name__)


def run(publisher, user, profile_json):
    """
    Check if a user mozillian's profile properly namespaces mozillians groups
    and whitelists which fields mozillians.org has authority over.

    :publisher: The CIS publisher
    :user: The user from the CIS vault
    :profile_json: The user profile passed by the publisher
    """

    # This plugin only cares about mozillians.org publisher
    if publisher != 'mozillians.org':
        return True

    ## Validate only whitelisted fields for this publisher are in use
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
        'groups'
    ]

    # Check for any non-whitelisted attribute modification
    # Note that no extra attribute may be added at this stage as we already performed schema validation
    for attr in user:
        if attr not in whitelist:
            if profile_json.get(attr) != user.get(attr):
                logger.exception('permission denied: publisher {} attempted to modify user attributes it has no'
                                 'authority over'.format(publisher))
                return False

    ## Validate namespaced groups only come from Mozillians.org
    # This is the whitelisted group prefix for this publisher:
    # group sub structure looks like: user.groups = [ 'group_from_ldap1', 'moziliansorg_mytestgroup', ...]
    prefix = 'mozilliansorg_'

    old_groups = user.get('groups')
    new_groups = profile_json.get('groups')

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
