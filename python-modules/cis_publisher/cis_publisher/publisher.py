import requests
import logging
import os
import time
from cis_profile.common import WellKnown
from cis_publisher import secret
from cis_publisher import common

logger = logging.getLogger(__name__)


class PublisherError(Exception):
    pass


class Publish:
    def __init__(self, profiles, login_method, publisher_name, discovery_url=None):
        """
        @profiles list of cis_profiles.User
        @login_method str a valid login_method for the user (such as "ad")
        @publisher_name str of your publisher name (such as 'ldap' or 'mozilliansorg')
        @user_ids list of str such as user_ids=['ad|bob|test', 'oauth2|alice|test', ..] which will be sent to CIS. When
        @discovery_url a discovery URL for CIS (CIS_DISCOVERY_URL env var will be used otherwise)
        """
        self.profiles = profiles
        self.login_method = login_method
        self.publisher_name = publisher_name
        if discovery_url is None:
            discovery_url = os.environ.get("CIS_DISCOVERY_URL", "https://auth.mozilla.com/.well-known/mozilla-iam")
        self.__discovery_url = discovery_url

        # Defaults
        self.api_url = None
        self.api_url_person = None
        self.api_url_change = None
        self.max_retries = 3
        # retry_delay is passed to time.sleep
        self.retry_delay = 1
        self.cis_user_list = None
        self.access_token = None
        self.known_cis_users = None
        self.__inited = False

    def __deferred_init(self):
        """
        Init all data that requires external resources
        """
        if self.__inited:
            return
        logger.info("Getting API URLs from well-known {}".format(self.__discovery_url))
        self.__well_known = WellKnown(self.__discovery_url)
        wk = self.__well_known.get_well_known()
        self.api_url = wk["api"]["endpoints"]
        self.api_audience = wk["api"]["audience"]
        self.api_url_person = self.api_url["person"]
        self.api_url_change = self.api_url["change"]
        self.publisher_rules = self.__well_known.get_publisher_rules()
        self.secret_manager = secret.Manager()
        self.config = common.get_config()
        self.__inited = True

    def post_all(self, user_ids=None):
        """
        Post all profiles
        @user_ids list of str which are user ids like 'ad|test'

        Returns list of failed users (empty if no failure)
        """

        self.__deferred_init()
        failed_users = []

        if user_ids is not None:
            logger.info("Requesting a specific list of user_id's to post {}".format(user_ids))
            if not isinstance(user_ids, list):
                raise PublisherError("user_ids must be a list", user_ids)

            for n in range(0, len(self.profiles)):
                profile = self.profiles[n]
                if profile.user_id.value not in user_ids:
                    del self.profiles[n]
            logger.info("After filtering, we have {} user profiles to post".format(len(self.profiles)))

        #        self.validate()

        access_token = self._get_authzero_token()
        qs = "/v2/user"
        cis_users = self.get_known_cis_users()

        for profile in self.profiles:
            # New users should also pass this parameter
            if profile.user_id.value in cis_users:
                qs = "/v2/user?user_id={}".format(profile.user_id.value)

            response_ok = False
            retries = 0
            while not response_ok:
                logger.info(
                    "Attempting to post profile {} to API {}{}".format(profile.user_id.value, self.api_url_change, qs)
                )
                response = self._request_post(
                    url="{}{}".format(self.api_url_change, qs),
                    payload=profile.as_dict(),
                    headers={"authorization": "Bearer {}".format(access_token)},
                )
                response_ok = response.ok
                if not response_ok:
                    logger.warning(
                        "Posting profile {} to API failed, retry is {} retry_delay is {}".format(
                            profile.user_id.value, retries, self.retry_delay
                        )
                    )
                    retries = retries + 1
                    time.sleep(self.retry_delay)
                    if retries >= self.max_retries:
                        logger.error(
                            "Maximum retries reached ({}), profile is not be sent {}".format(
                                retries, profile.user_id.value
                            )
                        )
                        failed_users.append(profile.user_id.value)
                        break
                else:
                    logger.info("Profile successfully posted to API {}".format(profile.user_id.value))
        return failed_users

    def _request_post(self, url, payload, headers):
        return requests.post(url, json=payload, headers=headers)

    def _request_get(self, url, qs, headers):
        return requests.get("{}{}".format(url, qs), headers=headers)

    def _get_authzero_client(self):
        authzero = secret.AuthZero(
            client_id=self.secret_manager.secret("client_id"),
            client_secret=self.secret_manager.secret("client_secret"),
            api_identifier=self.api_audience,
            authzero_tenant=self.config("authzero_tenant", namespace="cis", default="auth.mozilla.auth0.com"),
        )
        return authzero

    def _get_authzero_token(self):
        # This could check for expiration
        if self.access_token is not None:
            return self.access_token
        else:
            authzero = self._get_authzero_client()
            self.access_token = authzero.exchange_for_access_token()
            return self.access_token

    def get_known_cis_users(self):
        """
        Call CIS Person API and return a list of existing users
        """
        self.__deferred_init()
        if self.known_cis_users is not None:
            return self.known_cis_users

        logger.info("Requesting CIS Person API for a list of existing users for method {}".format(self.login_method))
        qs = "/v2/users/id/all?connectionMethod={}".format(self.login_method)
        access_token = self._get_authzero_token()
        response = self._request_get(
            self.api_url_person, qs, headers={"authorization": "Bearer {}".format(access_token)}
        )
        if not response.ok:
            logger.error(
                "Failed to query CIS Person API: {}{} response: {}".format(self.api_url_person, qs, response.text)
            )
            raise PublisherError("Failed to query CIS Person API", response.text)
        self.known_cis_users = response.json()
        return self.known_cis_users

    def filter_known_cis_users(self):
        """
        Filters out fields that are not allowed to be updated by this publisher from the profile before posting
        This is for "new" users
        """
        self.__deferred_init()

        if self.profiles is None:
            raise PublisherError("No profiles to operate on")

        cis_users = self.get_known_cis_users()

        # Never NULL/None these fields during filtering
        whitelist = ["user_id"]

        allowed_updates = self.publisher_rules["update"]
        for n in range(0, len(self.profiles)):
            p = self.profiles[n]
            if p.user_id.value in cis_users:
                logger.info(
                    "Filtering out non-updatable values from user {} because it already exist in CIS".format(
                        p.user_id.value
                    )
                )
                for pfield in p.__dict__:
                    # Skip? (see below for sub item)
                    if pfield in whitelist:
                        continue

                    if pfield not in allowed_updates:
                        continue

                    # sub-item?
                    elif pfield in ["identities", "staff_information", "access_information"]:
                        for subpfield in p.__dict__[pfield]:
                            # Skip?
                            if subpfield in whitelist:
                                continue

                            if allowed_updates[pfield] != self.publisher_name:
                                p.__dict__[pfield][subpfield]["signature"]["publisher"]["value"] = ""
                                if "value" in p.__dict__[pfield][subpfield].keys():
                                    p.__dict__[pfield][subpfield]["value"] = None
                                elif "values" in p.__dict__[pfield][subpfield].keys():
                                    p.__dict__[pfield][subpfield]["values"] = None
                    else:
                        if allowed_updates[pfield] != self.publisher_name:
                            p.__dict__[pfield]["signature"]["publisher"]["value"] = ""
                            if "value" in p.__dict__[pfield].keys():
                                p.__dict__[pfield]["value"] = None
                            elif "values" in p.__dict__[pfield].keys():
                                p.__dict__[pfield]["values"] = None
                logger.info("Filtered fields for user {}".format(p.user_id.value))
                self.profiles[n] = p

    def validate(self):
        """
        Validates all profiles are from the correct provider
        """
        logger.info("Validating {} profiles".format(len(self.profiles)))

        # XXX ensure ldap2s3 use the right login_method
        # then remove this
        lm_map = {"ad": ["Mozilla-LDAP", "Mozilla-LDAP-Dev"]}
        if self.login_method in lm_map:
            local_login_method = lm_map[self.login_method]
        else:
            local_login_method = [self.login_method]

        for profile in self.profiles:
            if profile.login_method.value not in local_login_method:
                logger.error(
                    "Incorrect login method for this user {} - looking for {} but got {}".format(
                        profile.user_id.value, local_login_method, profile.login_method.value
                    )
                )
        logger.info("Validation completed for all profiles")
