import cis_profile
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
        @login_method str a valid login_method for the user (such as "Mozilla-LDAP")
        @publisher_name str of your publisher name (such as 'ldap' or 'mozilliansorg')
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
        self.max_retries = 5
        # retry_delay is passed to time.sleep
        self.retry_delay = 5
        self.cis_user_list = None
        self.access_token = None
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

    def post_all(self):
        """
        Post all profiles
        """

        self.__deferred_init()
        self.validate()

        access_token = self._get_authzero_token()

        for profile in self.profiles:
            response_ok = False
            retries = 0
            while not response_ok:
                logger.info(
                    "Attempting to post profile {} to API {}".format(profile.user_id.value, self.api_url_change)
                )
                response = self._request_post(
                    self.api_url_change,
                    data=profile.as_json(),
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
                        raise PublisherError("Failed to publish profile")

    def _request_post(self, url, payload, headers):
        return requests.post(url, payload, headers)

    def _request_get(self, url, qs, headers):
        return requests.get("{}/{}".format(url, qs), headers)

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

        logger.info("Requesting CIS Person API for a list of existing users for method {}".format(self.login_method))
        qs = "/v2/users/id/all?connectionMethod={}".format(self.login_method)
        access_token = self._get_authzero_token()
        response = self._request_get(
            self.api_url_person, qs, headers={"authorization": "Bearer {}".format(access_token)}
        )
        if not response.ok:
            logger.error(
                "Failed to query CIS Person API: {}/{} response: {}".format(self.api_url_person, qs, response.text)
            )
            raise PublisherError("Failed to query CIS Person API", response.text)
        return response.json()

    def filter_known_cis_users(self):
        """
        Filters out fields that are not allowed to be updated by this publisher from the profile before posting
        This is for "new" users
        """
        self.__deferred_init()

        if self.profiles is None:
            raise PublisherError("No profiles to operate on")

        cis_users = self.get_known_cis_users()

        allowed_updates = self.publisher_rules["update"]
        for n in range(0, len(self.profiles)):
            p = self.profiles[n]
            if p.user_id.value in cis_users:
                logger.info(
                    "Filtering out non-updateable values from user {} because it already exist in CIS".format(
                        p.user_id.value
                    )
                )
                for pfield in p.__dict__:
                    if pfield not in allowed_updates:
                        continue

                    # sub-item?
                    if isinstance(allowed_updates[pfield], dict):
                        for subpfield in allowed_updates[pfield]:
                            if allowed_updates[pfield][subpfield] != self.publisher_name:
                                if "value" in p.__dict__[pfield][subpfield].keys():
                                    p.__dict__[pfield][subpfield]["value"] = None
                                elif "values" in p.__dict__[pfield][subpfield].keys():
                                    p.__dict__[pfield][subpfield]["values"] = None
                    else:
                        if allowed_updates[pfield] != self.publisher_name:
                            if "value" in p.__dict__[pfield].keys():
                                p.__dict__[pfield]["value"] = None
                            elif "values" in p.__dict__[pfield].keys():
                                p.__dict__[pfield]["values"] = None
                logger.info("Filtered fields for user {}".format(p.user_id.value))
                self.profiles[n] = p

    def validate(self):
        """
        Validates all profiles
        """
        logger.info("Validating {} profiles".format(len(self.profiles)))
        null_user = cis_profile.User()

        for profile in self.profiles:
            if profile.login_method.value != self.login_method:
                logger.error(
                    "Incorrect login method for this user {} - looking for {} but got {}".format(
                        profile.user_id.value, self.login_method, profile.login_method.value
                    )
                )
            profile.validate()
            profile.verify_all_signatures()
            # This should normally work since it's always like a create (even for update)
            profile.verify_all_publishers(null_user)
        logger.info("Validation completed for all profiles")
