"""Demonstrates a sample of publishing an event to kinesis and handling the response."""
import boto3
import logging
import os
import random
import subprocess
from boto.kinesis.exceptions import ResourceInUseException
from botocore.exceptions import ClientError
from botocore.stub import Stubber
from datetime import timedelta
from datetime import tzinfo

from cis_profile import fake_profile

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)


class simple_utc(tzinfo):
    def tzname(self, **kwargs):
        return "UTC"

    def utcoffset(self, dt):
        return timedelta(0)


class TestFullPublish(object):
    """Test sending a full profile with all the required attributes."""

    def setup_class(self):
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis.ini"
        from cis_publisher.common import get_config
        os.environ['CIS_KINESALITE_PORT'] = str(random.randint(32000, 34000))

        config = get_config()
        self.kinesalite_port = config('kinesalite_port', namespace='cis')
        self.kinesaliteprocess = subprocess.Popen(["kinesalite", "--port", self.kinesalite_port], preexec_fn=os.setsid)

        stub = Stubber(boto3.session.Session(region_name="us-west-2"))
        conn = stub.client.client("kinesis", endpoint_url="http://localhost:{}".format(kinesalite_port))

        try:
            name = "local-stream"
            conn.create_stream(StreamName=name, ShardCount=1)
        except ResourceInUseException:
            # This just means we tried too many tests too fast.
            pass
        except ClientError:
            pass

        waiter = conn.get_waiter("stream_exists")

        waiter.wait(StreamName=name, Limit=100, WaiterConfig={"Delay": 5, "MaxAttempts": 5})

        tags_1 = {"Key": "cis_environment", "Value": "local"}
        tags_2 = {"Key": "application", "Value": "change-stream"}
        conn.add_tags_to_stream(StreamName=name, Tags=tags_1)
        conn.add_tags_to_stream(StreamName=name, Tags=tags_2)

    def test_publishing_it_should_succeed(self):
        from cis_publisher import operation

        o = operation.Publish()

        # open the full-profile
        profile_json = fake_profile.FakeUser().as_dict()

        # modify an attribute
        profile_json["last_name"]["value"] = "AFakeLastName"

        # send to kinesis
        result = o.to_stream(profile_json)

        assert result.get("status_code") == 200
        assert result.get("sequence_number") is not None

    def test_publishing_it_should_fail(self):
        from cis_publisher import operation

        o = operation.Publish()

        # open the full-profile
        profile_json = fake_profile.FakeUser().as_dict()

        # modify an attribute
        profile_json["last_name"]["value"] = ["ImBadDataandICannotlie"]

        # send to kinesis
        result = o.to_stream(profile_json)

        assert result.get("status_code") == 400
        assert result.get("sequence_number") is None

    def test_publishing_stream_not_found(self):
        from cis_publisher import operation

        o = operation.Publish()

        profile_json = fake_profile.FakeUser().as_dict()

        # send to kinesis
        o._connect()
        o.kinesis_client["arn"] = "foo/foo"
        result = o.to_stream(profile_json)

        assert result.get("status_code") == 500
        assert result.get("sequence_number") is None

    def test_super_weird_parititon_key(self):
        from cis_publisher import operation

        o = operation.Publish()
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis-bad.ini"

        # open the full-profile
        profile_json = fake_profile.FakeUser().as_dict()

        # send to kinesis
        o._connect()
        result = o.to_stream(profile_json)

        assert result.get("status_code") == 200
        assert result.get("sequence_number") is not None

    def test_batch_publishing(self):
        from cis_publisher import operation

        o = operation.Publish()
        os.environ["CIS_CONFIG_INI"] = "tests/mozilla-cis-bad.ini"

        profiles = []
        for x in range(0, 10):
            profiles.append(fake_profile.FakeUser().as_dict())

        # send to kinesis
        o._connect()
        results = o.to_stream_batch(profiles)
        for result in results:
            assert result["sequence_number"] is not None
            assert result["status_code"] is not None

    def teardown_class(self):
        os.killpg(os.getpgid(self.kinesaliteprocess.pid), 15)
