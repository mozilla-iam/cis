import requests
import logging
import os
import time
import threading
import queue
from urllib.parse import urlencode, quote_plus
from cis_profile.common import WellKnown
from cis_profile import User
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
        self.access_token = None

        # Number of retries when calling CIS APIs, for robustness
        self.max_retries = 3
        self.max_threads = 50
        # retry_delay is passed to time.sleep
        self.retry_delay = 1

        # known_cis_users is the output of the Person API query
        # known_cis_users_by_user_id is a dict that maps user_id: email
        # known_cis_users_by_email is a dict that maps email: user_id (instead of user_id: email)
        self.cis_user_list = None
        self.known_cis_users = None
        self.known_cis_users_by_email = {}
        self.known_cis_users_by_user_id = {}
        self.all_known_profiles = {}
        self.__inited = False

    def __deferred_init(self):
        """
        Init all data that requires external resources
        """
        if self.__inited:
            return
        logger.info("Getting API URLs from well-known {}".format(self.__discovery_url))
        self.secret_manager = secret.Manager()
        self.config = common.get_config()
        self.__well_known = WellKnown(self.__discovery_url)
        wk = self.__well_known.get_well_known()
        self.api_url = wk["api"]["endpoints"]
        # XXX These are not currently used
        # self.api_audience = wk["api"]["audience"]
        # self.api_url_person = self.api_url["person"]
        # self.api_url_change = self.api_url["change"]
        self.api_audience = self.config("api_identifier", namespace="cis", default="api.dev.sso.allizom.org")
        self.api_url_person = "https://" + self.config(
            "person_api_url", namespace="cis", default="person.api.dev.sso.allizom.org"
        )
        self.api_url_change = "https://" + self.config(
            "change_api_url", namespace="cis", default="change.api.dev.sso.allizom.org"
        )
        self.publisher_rules = self.__well_known.get_publisher_rules()
        self.__inited = True

    def post_all(self, user_ids=None):
        """
        Post all profiles
        @user_ids list of str which are user ids like 'ad|test'

        Returns list of failed users (empty if no failure)
        """

        self.__deferred_init()
        qs = "/v2/user"

        threads = []
        failed_users = queue.Queue()

        logger.info("Received {} user profiles to post".format(len(self.profiles)))
        if user_ids is not None:
            logger.info(
                "Requesting a specific list of user_id's to post {} (total user_ids: {}, total profiles: {})".format(
                    user_ids, len(user_ids), len(self.profiles)
                )
            )
            if not isinstance(user_ids, list):
                raise PublisherError("user_ids must be a list", user_ids)

            # list what to delete, then delete instead of slower copy list operations or filters
            # This is because some data sets are huge / GBs of data
            xlist = []
            for idx, profile in enumerate(self.profiles):
                if profile.user_id.value is None:
                    if self.known_cis_users_by_email.get(profile.primary_email.value) not in user_ids:
                        xlist.append(idx)
                elif profile.user_id.value not in user_ids:
                    xlist.append(idx)
            for i in reversed(xlist):
                del self.profiles[i]
            logger.info("After filtering, we have {} user profiles to post".format(len(self.profiles)))

        # XXX - we already validate in the API, is this needed?
        #        self.validate()

        for profile in self.profiles:
            # If we have no user_id provided we need to find it here
            # These are always considered updated users, not new users
            if profile.user_id.value is None:
                user_id = self.known_cis_users_by_email[profile.primary_email.value]
            else:
                user_id = profile.user_id.value

            # Filter out non-updatable attributes as needed
            self.filter_known_cis_users(profiles=[profile])

            threads.append(threading.Thread(target=self._really_post, args=(user_id, qs, profile, failed_users)))
            threads[-1].start()
            num_threads = len(threading.enumerate())
            while num_threads >= self.max_threads:
                time.sleep(1)
                num_threads = len(threading.enumerate())
                logger.info("Too many concurrent threads, waiting a bit...")

        logger.debug("Waiting for threads to terminate...")
        for t in threads:
            t.join()
        logger.debug("Retrieving results from the queue...")
        ret = []
        while not failed_users.empty():
            ret.append(failed_users.get())
            failed_users.task_done()
        return ret

    def _really_post(self, user_id, qs, profile, failed_users):
        response_ok = False
        retries = 0
        access_token = self._get_authzero_token()

        # Existing users (i.e. users to update) have to be passed as argument
        if user_id in self.known_cis_users_by_user_id:
            qs = "/v2/user?user_id={}".format(user_id)
        # New users do not
        else:
            qs = "/v2/user"
        # We don't always get a user_id set
        identifier = user_id
        if identifier is None:
            identifier = profile.primary_email.value
            if identifier is None:
                logger.critical("Could not find profile identifier!")

        logger.debug("Posting user profile: {}".format(profile.as_dict()))

        while not response_ok:
            logger.info(
                "Attempting to post profile (user_id: {}, primary_email: {} to API {}{}".format(
                    profile.user_id.value, profile.primary_email.value, self.api_url_change, qs
                )
            )
            response = self._request_post(
                url="{}{}".format(self.api_url_change, qs),
                payload=profile.as_dict(),
                headers={"authorization": "Bearer {}".format(access_token)},
            )
            response_ok = response.ok

            if not response_ok:
                logger.warning(
                    "Posting profile {} to API failed, retry is {} retry_delay is {} status_code is {} reason is {}"
                    "contents were {}".format(
                        identifier, retries, self.retry_delay, response.status_code, response.reason, response.text
                    )
                )
                retries = retries + 1
                time.sleep(self.retry_delay)
                if retries >= self.max_retries:
                    logger.error(
                        "Maximum retries reached ({}), profile is not to be sent {}".format(retries, identifier)
                    )
                    failed_users.put(identifier)
                    break
            else:
                logger.info(
                    "Profile successfully posted to API {}, status_code: {}".format(identifier, response.status_code)
                )

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

    def get_known_cis_users_paginated(self):
        """
        Call CIS Person API and return a list of all known profiles
        return: list of dict JSON profiles
        """
        self.__deferred_init()
        if len(self.all_known_profiles) > 0:
            return self.all_known_profiles

        logger.info("Requesting CIS Person API for a list of all user profiles")
        qs = "/v2/users"
        access_token = self._get_authzero_token()
        nextPage = ""

        while nextPage is not None:
            if nextPage != "":
                real_qs = "{}?nextPage={}".format(qs, nextPage)
            else:
                real_qs = qs
            response = self._request_get(
                self.api_url_person, real_qs, headers={"authorization": "Bearer {}".format(access_token)}
            )
            if not response.ok:
                logger.error(
                    "Failed to query CIS Person API: {}{} response: {}".format(
                        self.api_url_person, real_qs, response.text
                    )
                )
                raise PublisherError("Failed to query CIS Person API", response.text)
            response_json = response.json()
            for p in response_json["Items"]:
                self.all_known_profiles[p["user_id"]["value"]] = p
            nextPage = response_json.get("nextPage")

        logger.info("Got {} users known to CIS".format(len(self.all_known_profiles)))
        return self.all_known_profiles

    def get_known_cis_users(self):
        """
        Call CIS Person API and return a list of existing user ids and/or remails
        return: list of str: cis user ids
        """
        self.__deferred_init()
        if self.known_cis_users is not None:
            return self.known_cis_users

        logger.info("Requesting CIS Person API for a list of existing users for method {}".format(self.login_method))
        qs = "/v2/users/id/all?connectionMethod={}&active=True".format(self.login_method)
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
        logger.info("Got {} users known to CIS".format(len(self.known_cis_users)))

        # Also save copies that are easier to query directly
        for u in self.known_cis_users:
            self.known_cis_users_by_user_id[u["user_id"]] = u["primary_email"]
            self.known_cis_users_by_email[u["primary_email"]] = u["user_id"]

        return self.known_cis_users

    def get_cis_user(self, user_id):
        """
        Call CIS Person API and return the matching user profile
        @user_id str a user_id
        """
        self.__deferred_init()
        logger.info("Requesting CIS Person API for a user profile {}".format(user_id))
        access_token = self._get_authzero_token()
        qs = "/v2/user/user_id/{}".format(urlencode(user_id, quote_via=quote_plus))
        response = self._request_get(
            self.api_url_person, qs, headers={"authorization": "Bearer {}".format(access_token)}
        )
        if not response.ok:
            logger.error(
                "Failed to query CIS Person API: {}{} response: {}".format(self.api_url_person, qs, response.text)
            )
            raise PublisherError("Failed to query CIS Person API", response.text)
        return User(response.json())

    def filter_known_cis_users(self, profiles=None, save=True):
        """
        Filters out fields that are not allowed to be updated by this publisher from the profile before posting
        This is for "new" users
        """
        self.__deferred_init()
        self.get_known_cis_users()

        if profiles is None:
            profiles = self.profiles

        # Never NULL/None these fields during filtering as they're used for knowing where to post
        whitelist = ["user_id", "active"]

        allowed_updates = self.publisher_rules["update"]
        for n in range(0, len(profiles)):
            p = profiles[n]
            if p.user_id.value is None:
                user_id = self.known_cis_users_by_email[p.primary_email.value]
            else:
                user_id = p.user_id.value

            if user_id in self.known_cis_users_by_user_id:
                logger.debug(
                    "Filtering out non-updatable values from user {} because it already exist in CIS".format(user_id)
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

                            # XXX access_information.{hris,ldap, ...} - this needs refactor
                            exit_loop = False
                            if isinstance(allowed_updates[pfield], dict):
                                for sub_au in allowed_updates[pfield]:
                                    if (
                                        p.__dict__[pfield][subpfield]["signature"]["publisher"]["name"]
                                        == self.publisher_name
                                    ):
                                        exit_loop = True
                                        break
                            if exit_loop:
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
                logger.debug("Filtered fields for user {}".format(user_id))
                profiles[n] = p
        if save:
            self.profiles = profiles
        return profiles

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
