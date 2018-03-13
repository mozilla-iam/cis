import json
import logging
import time

from cis.libs import exceptions

try:
    # Python 2.X
    from httplib import HTTPSConnection
    from urllib import quote
except ImportError:
    # Python 3+
    from http.client import HTTPSConnection
    from urllib.parse import quote

logger = logging.getLogger(__name__)


class Person(object):
    """Retrieve data from person api as needed."""
    def __init__(self, person_api_config):
        """
        :param person_api_config, a dictionary of configuration information about how to connect to person_api
        """

        # Audience is either https://person-api.sso.mozilla.com or https://person-api.sso.allizom.org
        self.audience = person_api_config.get('audience')
        self.client_id = person_api_config.get('client_id')
        self.client_secret = person_api_config.get('client_secret')
        self.oauth2_domain = person_api_config.get('oauth2_domain')
        self.person_api_url = person_api_config.get('person_api_url')
        self.person_api_version = person_api_config.get('person_api_version')
        self.bearer_token = {}

    def get_bearer(self):
        conn = HTTPSConnection(self.oauth2_domain)
        payload = json.dumps(
            {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'audience': self.audience,
                'grant_type': 'client_credentials'
            }
        )

        headers = {'content-type': "application/json"}

        if self._refresh():
            conn.request("POST", "/oauth/token", payload, headers)
            res = conn.getresponse()
            if res.status == 200:
                data = res.read()
                self.bearer_token = {
                    'token': json.loads(data.decode('utf-8')),
                    'generated': int(time.time())
                }
            else:
                logger.error('Status of API request was: {}'.format(res.status))
                raise exceptions.AuthZeroUnavailable()

        return self.bearer_token.get('token')

    def _refresh(self):
        """If the token was fetched more than 15-minutes ago return a new token."""
        if self.bearer_token == {}:
            logger.debug('Bearer token for auth0 not present returning refresh TRUE.')
            return True

        if int(time.time()) - self.bearer_token.get('generated') > 900:
            logger.debug(
                'Bearer token for auth0 is older than 15-minutes returning refresh TRUE.'
            )
            return True
        else:
            logger.debug(
                'Bearer token for auth0 is does not need refresh returning TRUE.'
            )
            return False

    def get_userinfo(self, auth_zero_id):
        user_id = quote(auth_zero_id)

        conn = HTTPSConnection("{}".format(self.person_api_url))
        token = "Bearer {}".format(self.get_bearer().get('access_token'))

        headers = {'authorization': token}

        api_route = "/{version}/profile/{user_id}".format(
            version=self.person_api_version,
            user_id=user_id
        )

        conn.request("GET", api_route, headers=headers)

        res = conn.getresponse()

        if res.status == 200:
            data = res.read()
            try:
                profile = json.loads(json.loads(data.decode('utf-8')).get('body'))
            except TypeError:
                profile = {}
        else:
            logger.error('Status of API request was: {}'.format(res.status))
            profile = None

        return profile
