import cis_profile
import requests
import logging
import os
import time
from cis_profile.common import WellKnown
from cis_publisher import secret

logger = logging.getLogger(__name__)


class PublisherError(Exception):
    pass


class Publish:
    def __init__(self, profiles, discovery_url=None):
        """
        @profiles list of cis_profiles.User
        """
        self.profiles = profiles
        if discovery_url is None:
            discovery_url = os.environ.get("CIS_DISCOVERY_URL", "https://auth.mozilla.com/.well-known/mozilla-iam")
        self.__discovery_url = discovery_url
        self.__well_known = WellKnown(discovery_url)
        self.api_url = None
        self.api_url_person = None
        self.api_url_change = None
        self.max_retries = 5
        # retry_delay is passed to time.sleep
        self.retry_delay = 5
        self.secret_manager = secret.Manager()

    def get_api_urls(self):
        """
        Set api urls
        """
        logger.info("Getting API URLs from well-known {}".format(self.__discovery_url))
        wk = self.__well_known.get_well_known()
        self.api_url = wk["api"]["endpoints"]
        self.api_url_person = self.api_url["person"]
        self.api_url_change = self.api_url["change"]

    def post_all(self):
        """
        Post all profiles
        """

        self.validate()

        if self.api_url is None:
            self.get_api_urls()

        authzero = self._get_authzero_client()
        access_token = authzero.exchange_for_access_token()

        for profile in self.profiles:
            response_ok = False
            retries = 0
            while not response_ok:
                logger.info(
                    "Attempting to post profile {} to API {}".format(profile.user_id.value, self.api_url_change)
                )
                response = requests.post(
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

    def _get_authzero_client(self):
        authzero = secret.AuthZero(
            client_id=self.secret_manager.secret("client_id"),
            client_secret=self.secret_manager.secret("client_secret"),
            authzero_tenant=self.config("authzero_tenant", namespace="cis", default="auth.mozilla.auth0.com"),
        )
        return authzero

    def validate(self):
        """
        Validates all profiles
        """
        logger.info("Validating {} profiles".format(len(self.profiles)))
        null_user = cis_profile.User()

        for profile in self.profiles:
            profile.validate()
            profile.verify_all_signatures()
            profile.verify_all_publishers(null_user)
        logger.info("Validation completed for all profiles")
