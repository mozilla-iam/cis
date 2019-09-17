from cis_profile import User
import cis_publisher
import json
import mock
import os

EVENT = {
    "Records": [
        {
            "body": """{
                "eventName": "MODIFY",
                "dynamodb": {
                    "Keys": {"user_id": {"S": "email|123"}},
                    "NewImage": {
                        "groups": {
                            "L": [
                                {"S": "mozilliansorg_nda"},
                                {"S": "mozilliansorg_slack-access"},
                                {"S": "mozilliansorg_open-innovation"},
                                {"S": "hris_costcenter_666"},
                                {"S": "hris_is_staff"}
                            ]
                        },
                        "user_id": {"S": "email|123"}
                    }
                }
            }"""
        }
    ]
}


class FakeGetResponse:
    def __init__(self, ret=User().as_json(), ok=True):
        self.ret = ret
        self.ok = ok
        self.text = ""

    def json(self):
        return json.loads(self.ret)


class FakePostResponse:
    def __init__(self):
        self.status_code = 200
        self.ok = True

    def json(self):
        return json.loads("[]")


class TestMozilliansorgGroups:
    def setup(self):
        os.environ["CIS_CONFIG_INI"] = "tests/fixture/mozilla-cis.ini"

    def test_mozilliansorg_group_update_from(self):
        update = cis_publisher.MozilliansorgGroupUpdate.from_record(EVENT["Records"][0])
        assert update is not None
        assert update.typ == "MODIFY"
        assert update.groups == ["nda", "slack-access", "open-innovation"]
        assert update.user_id == "email|123"

    @mock.patch("cis_publisher.Publish._request_post")
    @mock.patch("cis_publisher.Publish._request_get")
    @mock.patch("cis_publisher.secret.Manager.secret")
    @mock.patch("cis_publisher.secret.AuthZero.exchange_for_access_token")
    def test_prepare_update(self, mock_authzero, mock_secrets, mock_request_get, mock_request_post):
        mock_authzero.return_value = "dinopark"
        mock_secrets.return_value = "is_pretty_cool"

        mock_request_post.return_value = FakePostResponse()
        mock_request_get.return_value = FakeGetResponse(User(user_id="email|123").as_json())

        update = cis_publisher.MozilliansorgGroupUpdate.from_record(EVENT["Records"][0])
        mozilliansorg_group_publisher = cis_publisher.MozilliansorgGroupsPublisher()
        update_profile = mozilliansorg_group_publisher._prepare_update(update)
        assert update_profile.user_id.value == update.user_id
        assert update_profile.access_information.mozilliansorg.metadata.display == "ndaed"
        assert len(update_profile.access_information.mozilliansorg["values"]) == 3

    @mock.patch("cis_publisher.Publish._request_post")
    @mock.patch("cis_publisher.Publish._request_get")
    @mock.patch("cis_publisher.secret.Manager.secret")
    @mock.patch("cis_publisher.secret.AuthZero.exchange_for_access_token")
    def test_prepare_update_on_not_existing_profile(
        self, mock_authzero, mock_secrets, mock_request_get, mock_request_post
    ):
        mock_authzero.return_value = "dinopark"
        mock_secrets.return_value = "is_pretty_cool"

        mock_request_post.return_value = FakePostResponse()
        mock_request_get.return_value = FakeGetResponse(ret="{}", ok=False)

        update = cis_publisher.MozilliansorgGroupUpdate.from_record(EVENT["Records"][0])
        mozilliansorg_group_publisher = cis_publisher.MozilliansorgGroupsPublisher()
        update_profile = mozilliansorg_group_publisher._prepare_update(update)

        mock_request_post.return_value = FakePostResponse()
        mock_request_get.return_value = FakeGetResponse(ret="{}", ok=True)

        update = cis_publisher.MozilliansorgGroupUpdate.from_record(EVENT["Records"][0])
        mozilliansorg_group_publisher = cis_publisher.MozilliansorgGroupsPublisher()
        update_profile = mozilliansorg_group_publisher._prepare_update(update)
        assert update_profile is None
        assert update_profile is None

    @mock.patch("cis_publisher.Publish._request_post")
    @mock.patch("cis_publisher.Publish._request_get")
    @mock.patch("cis_publisher.secret.Manager.secret")
    @mock.patch("cis_publisher.secret.AuthZero.exchange_for_access_token")
    def test_publish(self, mock_authzero, mock_secrets, mock_request_get, mock_request_post):
        mock_authzero.return_value = "dinopark"
        mock_secrets.return_value = "is_pretty_cool"

        mock_request_post.return_value = FakePostResponse()
        mock_request_get.return_value = FakeGetResponse(User(user_id="email|123").as_json())

        mozilliansorg_group_publisher = cis_publisher.MozilliansorgGroupsPublisher()
        mozilliansorg_group_publisher.publish(EVENT)
