import cis_profile
import cis_publisher
import boto3
import botocore
import logging
import lzma
import json
from traceback import format_exc

logger = logging.getLogger(__name__)


class LDAPPublisher:
    def __init__(self):
        self.secret_manager = cis_publisher.secret.Manager()

    def publish(self, user_ids=None):
        """
        Glue to create or fetch cis_profile.User profiles for this publisher
        Then pass everything over to the Publisher class
        None, ALL profiles are sent.
        @user_ids: list of str - user ids to publish. If None, all users are published.
        """
        logger.info("Starting LDAP Publisher")
        profiles_xz = self.fetch_from_s3()
        # If there are memory issues here, use lzma.LZMADecompressor() instead
        raw = lzma.decompress(profiles_xz)
        profiles_json = json.loads(raw)
        # Free some memory
        del profiles_xz
        del raw

        profiles = []
        logger.info("Processing {} profiles".format(len(profiles_json)))
        for p in profiles_json:
            str_p = json.dumps(profiles_json[p])
            if (user_ids is None) or (profiles_json[p]["user_id"]["value"] in user_ids):
                profiles.append(cis_profile.User(user_structure_json=str_p))

        logger.info("Will publish {} profiles".format(len(profiles)))
        publisher = cis_publisher.Publish(profiles, publisher_name="ldap", login_method="ad")
        failures = []
        try:
            publisher.filter_known_cis_users()
            failures = publisher.post_all(user_ids=user_ids)
        except Exception as e:
            logger.error("Failed to post_all() LDAP profiles. Trace: {}".format(format_exc()))
            raise e
        if len(failures) > 0:
            logger.error("Failed to post {} profiles: {}".format(len(failures), failures))

    def fetch_from_s3(self):
        """
        Fetches xz json data from S3 (ie ldap_blah.json.xz)
        Returns the xz bytestream
        """
        bucket = self.secret_manager.secret("bucket")
        bucket_key = self.secret_manager.secret("bucket_key")
        logger.info("Retrieving all LDAP profiles from S3 {}/{}".format(bucket, bucket_key))
        s3 = boto3.client("s3")
        data = None
        try:
            response = s3.get_object(Bucket=bucket, Key=bucket_key)
            data = response["Body"].read()
        except botocore.exceptions.ClientError as e:
            logger.error("Failed to get LDAP S3 file from {}/{} trace: {}".format(bucket, bucket_key, format_exc()))
            raise e

        return data
