import logging
import time
import json
import requests
from cis_notifications import common
from cis_notifications import secret


logger = logging.getLogger(__name__)


class Event(object):
    """Handle events from lambda and generate hooks out to publishers."""

    def __init__(self, event):
        """[summary]

        Arguments:
            object {[type]} -- [an instance of the event class.]
            event {[type]} -- [the event as ingested from the kinesis stream.]
            subscriptions {[type]} -- [list of urls to post notifications to.]
        """
        self.config = common.get_config()
        self.event = event
        self.secret_manager = secret.Manager()
        self.access_token = None

    def to_notification(self):
        """[summary]
        Transform the instance of the event from the stream into a notification payload.

        [return] JSON data structure to send using requests.
        """

        logger.debug("An event was received", extra={"event": self.event})

        updated_record = self.event.get("dynamodb")

        operation = "foxy"  # Just a place holder in case we have an unhandled event.

        if self.event.get("eventName") == "INSERT":
            operation = "create"

        if self.event.get("eventName") == "MODIFY":
            operation = "update"

        if self.event.get("eventName") == "DELETE":
            operation = "delete"

        if updated_record is not None:
            # Provided the event is the structure that
            notification = {
                "operation": operation,
                "id": updated_record["Keys"]["id"]["S"],
                "time": updated_record["ApproximateCreationDateTime"],
            }

            logger.debug("Notification generated.", extra={"notification": notification})

            return notification
        else:
            logger.debug("No notification generated.")
            return {}

    def send(self, notification):
        """[summary]
        Get the list of notification endpoints from the object constructor and send a POST with the json payload.

        Arguments:
            object {[type]} -- [an instance of the event class.]
            object {[notification]} -- [A json payload that you would like to send to the RP.]

        [return] Dictionary of status codes by publisher.
        """
        # Not in-memory access token?
        if not self.access_token:
            # Load whatever is in our secrets
            self.access_token_dict = json.loads(self.secret_manager.secretmgr("az_access_token"))

            # Check if what we had in secrets is still valid!
            # This includes 10s leeway for clock sync issues
            if float(self.access_token_dict["exp"]) < time.time() - 10:
                logger.info("Access token has expired, refreshing")
                authzero = self._get_authzero_client()
                self.access_token_dict = authzero.exchange_for_access_token()
                # Auth0 gives us the difference (expires_in) not a time stamp, so we need to calculate when the token
                # expires. On failure to read expires_in, just make it expire in 60s as fallback
                self.access_token_dict["exp"] = time.time() + float(self.access_token_dict.get("expires_in", 60.0))
                self.secret_manager.secretmgr_store("az_access_token", self.access_token_dict)
            else:
                logger.info("Re-using cached access token")
            self.access_token = self.access_token_dict["access_token"]

        if notification != {}:
            rp_urls = self.config(
                "rp_urls", namespace="cis", default="https://dinopark.k8s.dev.sso.allizom.org/events/update"
            )

            results = {}
            for url in rp_urls.split(","):
                result = self._notify_via_post(url, notification, self.access_token)
                results[url] = result
            return results

    def _get_authzero_client(self):
        authzero = secret.AuthZero(
            client_id=self.secret_manager.secret("client_id"),
            client_secret=self.secret_manager.secret("client_secret"),
            api_identifier=self.config("api_identifier", namespace="cis", default="hook.dev.sso.allizom.org"),
            authzero_tenant=self.config("authzero_tenant", namespace="cis", default="auth.mozilla.auth0.com"),
        )

        return authzero

    def _notify_via_post(self, url, json_payload, access_token):
        """[summary]
        Notify a single publisher of the user_id that was updated and return only the status code.

        Arguments:
            url {[type]} -- [the url of the publisher you woud like to notify.]
            json_payload {[type]} -- [the event to send to the publisher.]
        """

        try:
            response = requests.post(
                url, json=json_payload, headers={"authorization": "Bearer {}".format(access_token)}
            )
            return response.status_code
        except requests.exceptions.RequestException:
            return "Unknown"
        except requests.exceptions.HTTPError:
            return "HTTPError"
        except requests.exceptions.ConnectionError:
            return "ConnectionError"
        except requests.exceptions.Timeout:
            return "Timeout"
