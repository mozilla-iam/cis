import cis_profile
import cis_publisher
import boto3
import botocore
import os
import logging
import json
import time
from auth0.v3.authentication import GetToken
from auth0.v3.management import Auth0
from auth0.v3.exceptions import Auth0Error
from datetime import datetime, timezone, timedelta
from traceback import format_exc

# from http.client import HTTPConnection

logger = logging.getLogger(__name__)
# HTTPConnection.debuglevel = 1


class Auth0Publisher:
    def __init__(self, context={}):
        self.secret_manager = cis_publisher.secret.Manager()
        self.context = context
        self.report = None
        self.config = cis_publisher.common.get_config()
        self.s3_cache = None
        self.s3_cache_require_update = False
        # Only fields we care about for the user entries
        # auth0 field->cis field map
        self.az_cis_fields = {
            "created_at": "created",
            "given_name": "first_name",
            "family_name": "last_name",
            "name": None,
            "nickname": None,
            "user_id": "user_id",
            "email": "primary_email",
            "identities": "identities",
            "blocked": "active",
        }
        self.az_blacklisted_connections = ["Mozilla-LDAP", "Mozilla-LDAP-Dev"]
        self.az_whitelisted_connections = ["email", "github", "google-oauth2", "firefoxaccounts"]
        self.az_users = None
        self.all_cis_user_ids = None
        self.user_ids_only = None

    def get_s3_cache(self):
        """
        If cache exists and is not older than timedelta() then return it, else don't
        return: dict JSON
        """
        if self.s3_cache is not None:
            return self.s3_cache

        s3 = boto3.client("s3")
        bucket = os.environ.get("CIS_BUCKET_URL")
        cache_time = int(os.environ.get("CIS_AUTHZERO_CACHE_TIME_SECONDS", 120))
        recent = datetime.now(timezone.utc) - timedelta(seconds=cache_time)
        try:
            objects = s3.list_objects_v2(Bucket=bucket)
            # bucket has zero contents?
            if "Contents" not in objects:
                logger.info("No S3 cache present")
                return None
            # Recent file?
            for o in objects["Contents"]:
                if o["Key"] == "cache.json" and recent > o["LastModified"]:
                    logger.info(
                        f"S3 cache too old, not using ({recent} gt {o['LastModified']}"
                        f", was cached for: {cache_time}s)"
                    )
                    return None
            response = s3.get_object(Bucket=bucket, Key="cache.json")
            data = response["Body"].read()
        except botocore.exceptions.ClientError as e:
            logger.error("Could not find S3 cache file: {}".format(e))
            return None
        logger.info("Using S3 cache")
        self.s3_cache = json.loads(data)
        return self.s3_cache

    def save_s3_cache(self, data):
        """
        @data dict JSON
        """
        if self.s3_cache_require_update is False:
            return

        s3 = boto3.client("s3")
        bucket = os.environ.get("CIS_BUCKET_URL")
        s3.put_object(Bucket=bucket, Key="cache.json", Body=json.dumps(data))
        logger.info("Wrote S3 cache file")

    def publish(self, user_ids=None, chunk_size=100):
        """
        Glue to create or fetch cis_profile.User profiles for this publisher
        Then pass everything over to the Publisher class
        None, ALL profiles are sent.
        @user_ids: list of str - user ids to publish. If None, all users are published.
        @chunk_size: int when no user_id is selected, this is the size of the chunk/slice we'll create to divide the
        work between function calls (to self)
        """
        if user_ids is None:
            le = "All"
        else:
            le = len(user_ids)
        logger.info("Starting Auth0 Publisher [{} users]".format(le))
        # XXX login_method is overridden when posting the user or listing users, i.e. the one here does not matter
        publisher = cis_publisher.Publish([], login_method="github", publisher_name="auth0")

        # These are the users auth0 knows about
        self.az_users = self.fetch_az_users(user_ids)
        self.all_cis_user_ids = self.fetch_all_cis_user_ids(publisher)

        # Should we fan-out processing to multiple function calls?
        if user_ids is None:
            # Because we do not care about most attributes update, we only process new users, or users that will be
            # deactivated in order to save time. Note that there is (currently) no auth0 hook to notify of new user
            # event, so this (the auth0 publisher that is) function needs to be reasonably fast to avoid delays when
            # provisioning users
            # So first, remove all known users from the requested list
            user_ids_to_process_set = set(self.get_az_user_ids()) - set(self.all_cis_user_ids)
            az_user_ids_set = set(self.get_az_user_ids())
            # Add blocked users so that they get deactivated
            logger.info(
                "Converting filtering list, size of user_ids_to_process {}".format(len(user_ids_to_process_set))
            )
            for u in self.az_users:
                if u["user_id"] in az_user_ids_set:
                    if ("blocked" in u.keys()) and (u["blocked"] is True):
                        user_ids_to_process_set.add(u["user_id"])

            logger.info(
                "After filtering out known CIS users/in auth0 blocked users, we will process {} users".format(
                    len(user_ids_to_process_set)
                )
            )
            self.save_s3_cache({"az_users": self.az_users, "all_cis_user_ids": self.all_cis_user_ids})
            self.fan_out(publisher, chunk_size, list(user_ids_to_process_set))
        else:
            # Don't cache auth0 list if we're just getting a single user, so that we get the most up to date data
            # and because it's pretty fast for a single user
            if len(user_ids) == 1:
                os.environ["CIS_AUTHZERO_CACHE_TIME_SECONDS"] = "0"
                logger.info("CIS_AUTHZERO_CACHE_TIME_SECONDS was set to 0 (caching disabled) for this run")
            self.process(publisher, user_ids)

    def fetch_all_cis_user_ids(self, publisher):
        """
        Get all known CIS user ids for the whitelisted login methods
        This is here because CIS only returns user ids per specific login methods
        We also cache this
        """

        self.s3_cache = self.get_s3_cache()
        if self.s3_cache is not None:
            self.all_cis_user_ids = self.s3_cache["all_cis_user_ids"]
            return self.all_cis_user_ids
        if self.all_cis_user_ids is not None:
            return self.all_cis_user_ids

        # Not cached, fetch it
        self.s3_cache_require_update = True
        # These are the users CIS knows about
        self.all_cis_user_ids = []
        for c in self.az_whitelisted_connections:
            # FIXME we're not using the real login method here because
            # Code in the CIS Vault matches against the start of `user_id` instead of the actual login method
            # This is fine for most methods, except this one... ideally the code should change in the CIS Vault when it
            # uses something else than DynamoDB and is able to match efficiently on other attributes
            if c == "firefoxaccounts":
                c = "oauth2|firefoxaccounts"
            publisher.login_method = c
            publisher.get_known_cis_users(include_inactive=False)
            self.all_cis_user_ids += publisher.known_cis_users_by_user_id.keys()
            # Invalidate publisher memory cache
            publisher.known_cis_users = None
        # XXX in case we got duplicates for some reason, we uniquify
        self.all_cis_user_ids = list(set(self.all_cis_user_ids))
        logger.info("Got {} known CIS users for all whitelisted login methods".format(len(self.all_cis_user_ids)))
        return self.all_cis_user_ids

    def get_az_user_ids(self):
        """
        Extract a list of user_ids from a dict of auth0 users
        return: list of user_ids
        """
        if self.user_ids_only is not None:
            return self.user_ids_only

        self.user_ids_only = []
        for u in self.fetch_az_users():
            self.user_ids_only.append(u["user_id"])
        return self.user_ids_only

    def fetch_az_users(self, user_ids=None):
        """
        Fetches ALL valid users from auth0'z database
        Returns list of user attributes
        """
        # Memory cached?
        if self.az_users is not None:
            return self.az_users

        # S3 cached?
        self.get_s3_cache()
        if self.s3_cache is not None:
            self.az_users = self.s3_cache["az_users"]
            return self.az_users
        # Don't use cache for just one user
        if self.az_users is not None and (user_ids is not None and len(user_ids) != 1):
            return self.az_users

        # Not cached, fetch it
        if user_ids is not None and len(user_ids) != 1:
            self.s3_cache_require_update = True
        az_api_url = self.config("AUTHZERO_API", namespace="cis", default="auth-dev.mozilla.auth0.com")
        az_client_id = self.secret_manager.secret("az_client_id")
        az_client_secret = self.secret_manager.secret("az_client_secret")
        az_fields = self.az_cis_fields.keys()

        # Build the connection query (excludes LDAP)
        # Excluded: "Mozilla-LDAP", "Mozilla-LDAP-Dev"
        # Excluded: Old users without any group
        # This can also be retrieved from /api/v2/connections
        # Ignore non-verified `email` (such as unfinished passwordless flows) as we don't consider these to be valid
        # users
        exclusion_query = 'NOT (last_login:[* TO 2018-01-01] AND (groups:(everyone) OR NOT _exists_:"groups"))'
        az_query = exclusion_query + " AND email_verified:true AND ("
        t = ""
        for azc in self.az_whitelisted_connections:
            az_query = az_query + t + 'identities.connection:"{}"'.format(azc)
            t = " OR "
        az_query = az_query + ")"
        # NOTE XXX: There is no way to tell auth0's ES "don't include matches where the first identity.connection is a
        # blacklisted connection", so we do this instead. This 100% relies on auth0 user_ids NOT being opaque,
        # unfortunately
        az_query = az_query + ' AND NOT (user_id:"ad|*")'

        # Build query for user_ids if some are specified (else it gets all of them)
        # NOTE: We can't query all that many users because auth0 uses a GET query which is limited in size by httpd
        # (nginx - 8kb by default)
        if user_ids and len(user_ids) > 6:
            logger.warning(
                "Cannot query the requested number of user_ids from auth0, query would be too large. "
                "Querying all user_ids instead."
            )
            user_ids = None
        elif user_ids:
            logger.info("Restricting auth0 user query to user_ids: {}".format(user_ids))
            t = ""
            az_query = az_query + " AND ("
            for u in user_ids:
                az_query = az_query + t + 'user_id:"{}"'.format(u)
                t = " OR "
            az_query = az_query + ")"

        logger.debug("About to get Auth0 user list")
        az_getter = GetToken(az_api_url)
        az_token = az_getter.client_credentials(az_client_id, az_client_secret, "https://{}/api/v2/".format(az_api_url))
        auth0 = Auth0(az_api_url, az_token["access_token"])

        # Query the entire thing
        logger.info("Querying auth0 user database, query is: {}".format(az_query))
        p = 0
        user_list = []
        # This is an artificial upper limit of 100*9999 (per_page*page) i.e. 999 900 users max - just in case things
        # go wrong
        retries = 15
        backoff = 20
        for p in range(0, 9999):
            tmp = None
            try:
                tmp = auth0.users.list(page=p, per_page=100, fields=az_fields, q=az_query)["users"]
                logger.debug("Requesting auth0 user list, at page {}".format(p))
            except Auth0Error as e:
                # 429 is Rate limit exceeded and we can still retry
                if (e.error_code == 429 or e.status_code == 429) and retries > 0:
                    backoff = backoff + 1
                    logger.debug(
                        "Rate limit exceeded, backing off for {} seconds, retries left {} error: {}".format(
                            backoff, retries, e
                        )
                    )
                    retries = retries - 1
                    time.sleep(backoff)
                else:
                    logger.warning("Error: {}".format(e))
                    raise

            if tmp == [] or tmp is None:
                # stop when our page is empty
                logger.debug("Crawled {} pages from auth0 users API".format(p))
                break
            else:
                user_list.extend(tmp)
        logger.info("Received {} users from auth0".format(len(user_list)))

        self.az_users = user_list

        return self.az_users

    def convert_az_users(self, az_users):
        """
        Convert a list of auth0 user fields to cis_profile Users
        @az_users list of dicts with user attributes
        Returns [cis_profile.Users]
        """
        profiles = []
        logger.info("Converting auth0 users into CIS Profiles ({} user(s))".format(len(az_users)))

        for u in az_users:
            p = cis_profile.User()
            # Must have fields
            p.user_id.value = u["user_id"]
            p.user_id.signature.publisher.name = "access_provider"
            p.update_timestamp("user_id")
            p.active.value = True
            if "blocked" in u.keys():
                if u["blocked"]:
                    p.active.value = False
            p.active.signature.publisher.name = "access_provider"
            p.update_timestamp("active")

            p.primary_email.value = u["email"]
            p.primary_email.metadata.display = "private"
            p.primary_email.signature.publisher.name = "access_provider"
            p.update_timestamp("primary_email")
            try:
                p.login_method.value = u["identities"][0]["connection"]
                p.update_timestamp("login_method")
            except IndexError:
                logger.critical("Could not find login method for user {}, skipping integration".format(p.user_id.value))
                continue

            # Should have fields (cannot be "None" or "" but can be " ")
            tmp = u.get("given_name", u.get("name", u.get("family_name", u.get("nickname", " "))))
            p.first_name.value = tmp
            p.first_name.metadata.display = "private"
            p.first_name.signature.publisher.name = "access_provider"
            p.update_timestamp("first_name")

            tmp = u.get("family_name", " ")
            p.last_name.value = tmp
            p.last_name.metadata.display = "private"
            p.last_name.signature.publisher.name = "access_provider"
            p.update_timestamp("last_name")

            # May have fields (its ok if these are not set)
            tmp = u.get("node_id", None)
            if tmp is not None:
                p.identities.github_id_v4.value = tmp
                p.identities.github_id_v4.display = "private"
                p.identities.github_id_v4.signature.publisher.name = "access_provider"
                p.update_timestamp("identities.github_id_v4")
            if "identities" in u.keys():
                # If blacklisted connection is in the first entry, skip (first entry = "main" user)
                if u["identities"][0].get("connection") in self.az_blacklisted_connections:
                    logger.warning(
                        "ad/LDAP account returned from search - this should not happen. User will be skipped."
                        " User_id: {}".format(p.user_id.value)
                    )
                    continue
                for ident in u["identities"]:
                    if ident.get("provider") == "google-oauth2":
                        p.identities.google_oauth2_id.value = ident.get("user_id")
                        p.identities.google_oauth2_id.metadata.display = "private"
                        p.identities.google_oauth2_id.signature.publisher.name = "access_provider"
                        p.update_timestamp("identities.google_oauth2_id")
                        p.identities.google_primary_email.value = p.primary_email.value
                        p.identities.google_primary_email.metadata.display = "private"
                        p.identities.google_primary_email.signature.publisher.name = "access_provider"
                        p.update_timestamp("identities.google_primary_email")
                    elif ident.get("provider") == "oauth2" and ident.get("connection") == "firefoxaccounts":
                        p.identities.firefox_accounts_id.value = ident.get("user_id")
                        p.identities.firefox_accounts_id.metadata.display = "private"
                        p.identities.firefox_accounts_id.signature.publisher.name = "access_provider"
                        p.update_timestamp("identities.firefox_accounts_id")
                        p.identities.firefox_accounts_primary_email.value = p.primary_email.value
                        p.identities.firefox_accounts_primary_email.metadata.display = "private"
                        p.identities.firefox_accounts_primary_email.signature.publisher.name = "access_provider"
                        p.update_timestamp("identities.firefox_accounts_primary_email")
                    elif ident.get("provider") == "github":
                        if ident.get("nickname") is not None:
                            # Match the hack in
                            # https://github.com/mozilla-iam/dino-park-whoami/blob/master/src/update.rs#L42 (see
                            # function definition at the top of the file as well)
                            p.usernames.value = {"HACK#GITHUB": ident.get("nickname")}
                            p.usernames.metadata.display = "private"
                            p.usernames.signature.publisher.name = "access_provider"
                        p.identities.github_id_v3.value = ident.get("user_id")
                        p.identities.github_id_v3.metadata.display = "private"
                        p.identities.github_id_v3.signature.publisher.name = "access_provider"
                        p.update_timestamp("identities.github_id_v3")
                        if "profileData" in ident.keys():
                            p.identities.github_primary_email.value = ident["profileData"].get("email")
                            p.identities.github_primary_email.metadata.verified = ident["profileData"].get(
                                "email_verified", False
                            )
                            p.identities.github_primary_email.metadata.display = "private"
                            p.identities.github_primary_email.signature.publisher.name = "access_provider"
                            p.update_timestamp("identities.github_primary_email")
                            p.identities.github_id_v4.value = ident["profileData"].get("node_id")
                            p.identities.github_id_v4.metadata.display = "private"
                            p.identities.github_id_v4.signature.publisher.name = "access_provider"
                            p.update_timestamp("identities.github_id_v4")

            # Sign and verify everything
            try:
                p.sign_all(publisher_name="access_provider")
            except Exception as e:
                logger.critical(
                    "Profile data signing failed for user {} - skipped signing, verification "
                    "WILL FAIL ({})".format(p.primary_email.value, e)
                )
                logger.debug("Profile data {}".format(p.as_dict()))

            try:
                p.validate()
            except Exception as e:
                logger.critical(
                    "Profile schema validation failed for user {} - skipped validation, verification "
                    "WILL FAIL({})".format(p.primary_email.value, e)
                )
                logger.debug("Profile data {}".format(p.as_dict()))

            try:
                p.verify_all_publishers(cis_profile.User())
            except Exception as e:
                logger.critical(
                    "Profile publisher verification failed for user {} - skipped signing, verification "
                    "WILL FAIL ({})".format(p.primary_email.value, e)
                )
                logger.debug("Profile data {}".format(p.as_dict()))

            logger.debug("Profile signed and ready to publish for user_id {}".format(p.user_id.value))
            profiles.append(p)
        logger.info("All profiles in this request were converted to CIS Profiles")
        return profiles

    def process(self, publisher, user_ids):
        """
        Process profiles and post them
        @publisher object the publisher object to operate on
        @user_ids list of user ids to process in this batch
        """

        # Only process the requested user_ids from the list of all az users
        # as the list is often containing all users, not just the ones we requested
        todo_user_ids = list(set(self.get_az_user_ids()) & set(user_ids))
        todo_users = []
        for u in self.az_users:
            if u["user_id"] in todo_user_ids:
                todo_users.append(u)

        profiles = self.convert_az_users(todo_users)
        logger.info("Processing {} profiles".format(len(profiles)))
        publisher.profiles = profiles

        failures = []
        try:
            failures = publisher.post_all(user_ids=user_ids, create_users=True)
        except Exception as e:
            logger.error("Failed to post_all() profiles. Trace: {}".format(format_exc()))
            raise e

        if len(failures) > 0:
            logger.error("Failed to post {} profiles: {}".format(len(failures), failures))

    def fan_out(self, publisher, chunk_size, user_ids_to_process):
        """
        Splices all users to process into chunks
        and self-invoke as many times as needed to complete all work in parallel lambda functions
        When self-invoking, this will effectively call self.process() instead of self.fan_out()
"]
        Note: chunk_size should never result in the invoke() argument to exceed 128KB (len(Payload.encode('utf-8') <
        128KB) as this is the maximum AWS Lambda payload size.

        @publisher object the cis_publisher object to operate on
        @chunk_size int size of the chunk to process
        """
        sliced = [user_ids_to_process[i : i + chunk_size] for i in range(0, len(user_ids_to_process), chunk_size)]
        logger.info(
            "No user_id selected. Creating slices of work, chunk size: {}, slices: {}, total users: {} and "
            "faning-out work to self".format(chunk_size, len(sliced), len(user_ids_to_process))
        )
        lambda_client = boto3.client("lambda")
        for s in sliced:
            lambda_client.invoke(FunctionName=self.context.function_name, InvocationType="Event", Payload=json.dumps(s))
            time.sleep(3)  # give api calls a chance, otherwise this storms resources

        logger.info("Exiting slicing function successfully")
