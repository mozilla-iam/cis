import logging

logger = logging.getLogger(__name__)


def run(publisher, user, profile_json):
    """
    Check if a user mozillian's profile properly namespaces mozillians groups

    :publisher: The CIS publisher
    :user: The user from the CIS vault
    :profile_json: The user profile passed by the publisher
    """

    # This plugin only cares about mozillians.org publisher
    if publisher != 'mozillians.org':
        return True

    # XXX TODO Validate groups only come from Mozillians.org
    return True
