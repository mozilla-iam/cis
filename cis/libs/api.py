import http.client
import json
import urllib


class Person(object):
    """Retrieve data from person api as needed.  Will eventually replace Mozillians API"""
    def __init__(self, person_api_config):
        """
        :param person_api_config, a dictionary of configuration information about how to connect to person_api
        """

        # Audience is either https://person-api.sso.mozilla.com or https://person-api.sso.allizom.org
        self.audience = person_api_config.get('audience')
        self.client_id = person_api_config.get('client_id')
        self.client_secret = person_api_config.get('client_secret')
        self.oidc_domain = person_api_config.get('oidc_domain')
        self.person_api_url = person_api_config.get('person_api_url')

    def get_bearer(self):
        conn = http.client.HTTPSConnection(self.oidc_domain)
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
        data = res.read()
        return json.loads(data.decode('utf-8'))

    def get_userinfo(self, auth_zero_id):
        user_id = urllib.quote(auth_zero_id)
        conn = http.client.HTTPSConnection("{}".format(self.person_api_url))
        token = "Bearer {}".format(self.get_bearer().get('access_token'))

        headers = {'authorization': token}

        conn.request("GET", "/prod/profile/{}".format(user_id), headers=headers)

        res = conn.getresponse()

        if res.status == '200 OK':
            data = res.read()
            return json.loads(json.loads(data.decode('utf-8')).get('body'))
        else:
            return None
