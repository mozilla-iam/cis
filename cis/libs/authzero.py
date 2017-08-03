#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Copyright (c) 2017 Mozilla Corporation
# Contributors: Guillaume Destuynder <kang@mozilla.com>


# Auth0 setup
# Required client: non-interactive Auth0 client
# Required Auth0 API Scopes
# create:users (for users Auth0 does not yet know about)
# update:user_app_metadata (this is where the CIS data is stored)
# create:user_app_metadata (same reason)
# read:users (to read the original user data for [re]integration purposes)
#
# NOTE: we're not using update:users because it is not possible to update
# the attributes we care about directly. Instead we load the attributes we
# want into user_app_metadata, and have an auth0 rule that will overwrite
# the user profile data just-in-time when using/posting it.
# (instead of overwriting the user profile directly, which Auth0 does not let
# you do)

import http.client
import json
import time
import logging
import utils


class DotDict(dict):
    """
    returns a dict.item notation for dict()'s
    """
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

    def __init__(self, dct):
        for key, value in dct.items():
            if hasattr(value, 'keys'):
                value = DotDict(value)
            self[key] = value


class CISAuthZero():
    def __init__(self, config):
        self.default_headers = {
            'content-type': "application/json"
        }
        self.uri = config.uri
        self.client_id = config.client_id
        self.client_secret = config.client_secret
        self.access_token = None
        self.access_token_scope = None
        self.access_token_valid_until = 0
        self.conn = http.client.HTTPSConnection(config.uri)

        log_level = logging.INFO
        utils.set_stream_logger(level=log_level)
        self.logger = logging.getLogger('CISAuthZero')

    def __del__(self):
        self.client_secret = None
        self.conn.close()

    def get_user(self, user_id):
        """
        user_id: string
        returns: JSON dict of the user profile
        """

        payload = DotDict(dict())
        payload_json = json.dumps(payload)
        self.conn.request("GET",
                          "/api/v2/users/{}".format(user_id),
                          payload_json,
                          self._authorize(self.default_headers))
        res = self.conn.getresponse()
        self._check_http_response(res)
        user = DotDict(json.loads(res.read()))
        return user

    def update_user(self, user_id, new_profile):
        """
        user_id: string
        new_profile: dict (can be a JSON string loaded with json.loads(str) for example)

        Update a user in auth0 and return it as a dict to the caller.
        Auth0 API doc: https://auth0.com/docs/api/management/v2
        Auth0 API endpoint: PATCH /api/v2/users/{id}
        Auth0 API parameters: id (user_id, required), body (required)
        """

        payload = DotDict(dict())
        assert type(new_profile) is dict
        # Auth0 does not allow passing the user_id attribute
        # as part of the payload (it's in the PATCH query already)
        if 'user_id' in new_profile.keys():
            del new_profile['user_id']
        payload.app_metadata = new_profile
        # This validates the JSON as well
        payload_json = json.dumps(payload)

        self.conn.request("PATCH",
                          "/api/v2/users/{}".format(user_id),
                          payload_json,
                          self._authorize(self.default_headers))
        res = self.conn.getresponse()
        self._check_http_response(res)
        user = DotDict(json.loads(res.read()))
        return user

    def get_access_token(self):
        """
        Returns a JSON object containing an OAuth access_token.
        This is also stored in this class other functions to use.
        """
        payload = DotDict(dict())
        payload.client_id = self.client_id
        payload.client_secret = self.client_secret
        payload.audience = "https://{}/api/v2/".format(self.uri)
        payload.grant_type = "client_credentials"
        payload_json = json.dumps(payload)

        self.conn.request("POST", "/oauth/token", payload_json, self.default_headers)
        res = self.conn.getresponse()
        self._check_http_response(res)

        access_token = DotDict(json.loads(res.read()))
        # Validation
        if ('access_token' not in access_token.keys()):
            raise Exception('InvalidAccessToken', access_token)
        self.access_token = access_token.access_token
        self.access_token_valid_until = time.time() + access_token.expires_in
        self.access_token_scope = access_token.scope
        return access_token

    def _authorize(self, headers):
        if not self.access_token:
            raise Exception('InvalidAccessToken')
        if self.access_token_valid_until < time.time():
            raise Exception('InvalidAccessToken', 'The access token has expired')

        local_headers = {}
        local_headers.update(headers)
        local_headers['Authorization'] = 'Bearer {}'.format(self.access_token)

        return local_headers

    def _check_http_response(self, response):
        """Check that we got a 2XX response from the server, else bail out"""
        if (response.status >= 300) or (response.status < 200):
            self.logger.debug(
                "_check_http_response() HTTP communication failed: {} {}".format(
                    response.status, response.reason, response.read()
                )
            )
            raise Exception('HTTPCommunicationFailed', (response.status, response.reason))
