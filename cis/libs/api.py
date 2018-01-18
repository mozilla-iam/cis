import http.client
import json

from cis.libs import exceptions

try:
    from urllib import quote  # Python 2.X
except ImportError:
    from urllib.parse import quote  # Python 3+


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

    def get_bearer(self):
        conn = http.client.HTTPSConnection(self.oauth2_domain)
        payload = json.dumps(
            {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'audience': self.audience,
                'grant_type': 'client_credentials'
            }
        )

        headers = {'content-type': "application/json"}
        conn.request("POST", "/oauth/token", payload, headers)

        res = conn.getresponse()
        if res.status == '200 OK':
            data = res.read()
            return json.loads(data.decode('utf-8'))
        else:
            raise exceptions.AuthZeroUnavailable()

    def get_userinfo(self, auth_zero_id):
        user_id = quote(auth_zero_id)

        conn = http.client.HTTPSConnection("{}".format(self.person_api_url))
        token = "Bearer {}".format(self.get_bearer().get('access_token'))

        headers = {'authorization': token}

        api_route = "/{version}/profile/{user_id}".format(
            version=self.person_api_version,
            user_id=user_id
        )

        conn.request("GET", api_route, headers=headers)

        res = conn.getresponse()

        if res.status == '200 OK':
            data = res.read()
            return json.loads(json.loads(data.decode('utf-8')).get('body'))
        else:
            return None
