import cis_notifications
import json
import mock


class TestNotifier(object):
    @mock.patch("cis_notifications.event.Event._notify_via_post")
    @mock.patch("cis_notifications.secret.Manager.secret")
    @mock.patch("cis_notifications.secret.AuthZero.exchange_for_access_token")
    def test_event_to_request(self, mock_authzero, mock_secrets, mock_request):
        """Test ingesting the event from the lambda function event handler and transforming it into a request.

        Arguments:
            object {[object]} -- [Takes an instance of the testNotifier object and asserts about the behavior.]
        """

        mock_authzero.return_value = "dinopark"
        mock_secrets.return_value = "is_pretty_cool"
        mock_request.return_value = 200

        # This is an example of a event as ingested from the dynamodb stream.
        subscriptions = ["https://dinopark.k8s.sso.allizom.org/beta/"]

        fh = open("tests/fixtures/event.json")
        event_fixture = json.loads(fh.read())
        fh.close()

        for record in event_fixture["Records"]:
            e = cis_notifications.event.Event(event=record, subscriptions=subscriptions)
            notification = e.to_notification()
            result = e.send(notification)

            assert notification is not None
            assert result is not None
            assert result["https://dinopark.k8s.dev.sso.allizom.org/events/update"] == 200
