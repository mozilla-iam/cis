"""Simple profile publishing script to demonstrate how to use the profilev2 cisv2 developer preview"""

import request
from logging import getLogger
from cis_profile import profile

logger = getLogger(__name__)


CHANGE_ENDPOINT = ""
PROFILE_API_ENDPOINT = ""


# Load fixture

for profile in fixture:
    # do stuff
