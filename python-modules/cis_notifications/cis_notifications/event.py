import requests
from cis_notifications import common
from cis_notifications import secret


class Event(object):
    """Handle events from lambda and generate hooks out to publishers."""

    def __init__(self, event, subscriptions):
        """[summary]

        Arguments:
            object {[type]} -- [an instance of the event class.]
            event {[type]} -- [the event as ingested from the kinesis stream.]
            subscriptions {[type]} -- [list of urls to post notifications to.]
        """
        self.config = common.get_config()
        self.event = event
        self.subscriptions = subscriptions
        self.secret_manager = secret.Manager()

    def to_notification(self):
        """[summary]
        Transform the instance of the event from the stream into a notification payload.

        [return] JSON data structure to send using requests.
        """

        logger.debug("An event was received", extra={"event": self.event})

        updated_record = self.event.get("dynamodb")

        operation = "foxy"

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

        if notification != {}:
            rp_urls = self.config(
                "rp_urls", namespace="cis", default="https://dinopark.k8s.dev.sso.allizom.org/events/update"
            )
            authzero = self._get_authzero_client()
            access_token = authzero.exchange_for_access_token()
            results = {}
            for url in rp_urls.split(","):
                result = self._notify_via_post(url, notification, access_token)
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
        response = requests.post(url, json=json_payload, headers={"authorization": "Bearer {}".format(access_token)})
        return response.status_code
