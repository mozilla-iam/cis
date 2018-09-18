"""Demonstrates a sample of publishing an event to kinesis and handling the response."""
import boto3
import json
import os
import subprocess
from boto.kinesis.exceptions import ResourceInUseException
from botocore.stub import Stubber
from datetime import datetime
from datetime import timedelta
from datetime import tzinfo


class simple_utc(tzinfo):
    def tzname(self, **kwargs):
        return "UTC"

    def utcoffset(self, dt):
        return timedelta(0)


class TestFullPublish(object):
    """Test sending a full profile with all the required attributes."""
    def setup_class(self):
        os.environ['CIS_CONFIG_INI'] = 'tests/mozilla-cis.ini'
        from cis_publisher import get_config
        config = get_config()
        kinesalite_port = config('kinesalite_port', namespace='cis')
        kinesalite_host = config('kinesalite_host', namespace='cis')
        subprocess.Popen(['kinesalite', '--port', kinesalite_port])

        conn = Stubber(
                boto3.session.Session(
                    region_name='us-west-2'
                )
        ).client.client(
            'kinesis',
            endpoint_url='http://localhost:{}'.format(kinesalite_port).format(
                kinesalite_host,
                kinesalite_port
            )
        )

        try:
            name = 'local-stream'
            conn.create_stream(
                StreamName=name,
                ShardCount=1
            )
        except ResourceInUseException:
            # This just means we tried too many tests too fast.
            pass

        waiter = conn.get_waiter('stream_exists')

        waiter.wait(
            StreamName=name,
            Limit=100,
            WaiterConfig={
                'Delay': 30,
                'MaxAttempts': 5
            }
        )

        tags_1 = {'Key': 'cis_environment', 'Value': 'local'}
        tags_2 = {'Key': 'application', 'Value': 'change-stream'}
        conn.add_tags_to_stream(StreamName=name, Tags=tags_1)
        conn.add_tags_to_stream(StreamName=name, Tags=tags_2)

    def test_publishing_it_should_succeed(self):
        from cis_publisher import operation
        o = operation.Publish()

        # open the full-profile
        fh = open('tests/fixture/full-profile.json')
        profile_json = json.loads(fh.read())
        fh.close()

        # modify an attribute
        profile_json['last_name']['value'] = 'AFakeLastName'

        # regenerate metadata
        d = datetime.utcnow().replace(tzinfo=simple_utc()).isoformat()
        str(d).replace('+00:00', 'Z')
        metadata = {
              "classification": "PUBLIC",
              "last_modified": "{}".format(d),
              "created": "2018-01-01T00:00:00Z",
              "publisher_authority": "cis",
              "verified": True
        }

        profile_json['last_name']['metadata'] = metadata

        # send to kinesis
        result = o.to_stream(profile_json)

        assert result.get('status_code') == 200
        assert result.get('sequence_number') is not None

    def test_publishing_it_should_fail(self):
        from cis_publisher import operation
        o = operation.Publish()

        # open the full-profile
        fh = open('tests/fixture/full-profile.json')
        profile_json = json.loads(fh.read())
        fh.close()

        # modify an attribute
        profile_json['last_name']['value'] = [
            'ImBadDataandICannotlie'
        ]
        # regenerate metadata
        d = datetime.utcnow().replace(tzinfo=simple_utc()).isoformat()
        str(d).replace('+00:00', 'Z')
        metadata = {
              "classification": "PUBLIC",
              "last_modified": "{}".format(d),
              "created": "2018-01-01T00:00:00Z",
              "publisher_authority": "cis",
              "verified": True
        }

        profile_json['last_name']['metadata'] = metadata

        # send to kinesis
        result = o.to_stream(profile_json)

        assert result.get('status_code') == 400
        assert result.get('sequence_number') is None

    def test_publishing_stream_not_found(self):
        from cis_publisher import operation
        o = operation.Publish()

        # open the full-profile
        fh = open('tests/fixture/full-profile.json')
        profile_json = json.loads(fh.read())
        fh.close()

        # regenerate metadata
        d = datetime.utcnow().replace(tzinfo=simple_utc()).isoformat()
        str(d).replace('+00:00', 'Z')
        metadata = {
              "classification": "PUBLIC",
              "last_modified": "{}".format(d),
              "created": "2018-01-01T00:00:00Z",
              "publisher_authority": "cis",
              "verified": True
        }

        profile_json['last_name']['metadata'] = metadata

        # send to kinesis
        o._connect()
        o.kinesis_client['arn'] = 'foo/foo'
        result = o.to_stream(profile_json)

        assert result.get('status_code') == 404
        assert result.get('sequence_number') is None

    def test_super_weird_parititon_key(self):
        from cis_publisher import operation
        o = operation.Publish()
        os.environ['CIS_CONFIG_INI'] = 'tests/mozilla-cis-bad.ini'

        # open the full-profile
        fh = open('tests/fixture/full-profile.json')
        profile_json = json.loads(fh.read())
        fh.close()

        # regenerate metadata
        d = datetime.utcnow().replace(tzinfo=simple_utc()).isoformat()
        str(d).replace('+00:00', 'Z')
        metadata = {
              "classification": "PUBLIC",
              "last_modified": "{}".format(d),
              "created": "2018-01-01T00:00:00Z",
              "publisher_authority": "cis",
              "verified": True
        }

        profile_json['last_name']['metadata'] = metadata

        # send to kinesis
        o._connect()
        result = o.to_stream(profile_json)

        assert result.get('status_code') == 200
        assert result.get('sequence_number') is not None

    def teardown_class(self):
        subprocess.Popen(['killall', 'node'])
