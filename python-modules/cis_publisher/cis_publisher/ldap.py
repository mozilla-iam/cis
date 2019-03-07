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

    def publish(self):
        """
        Glue to create or fetch cis_profile.User profiles for this publisher
        Then pass everything over to the Publisher class
        None, ALL profiles are sent.
        """
        profiles_xz = self.fetch_from_s3()
        # If there are memory issues here, use lzma.LZMADecompressor() instead
        raw = lzma.decompress(profiles_xz)
        profiles_json = json.loads(raw)
        # Free some memory
        del profiles_xz
        del raw

        profiles = []
        for p in profiles_json:
            str_p = json.dumps(profiles_json[p])
            profiles.append(cis_profile.User(user_structure_json=str_p))

        publisher = cis_publisher.Publish(profiles, publisher_name="ldap", login_method="Mozilla-LDAP")
        try:
            publisher.filter_known_cis_users()
            publisher.post_all()
        except Exception as e:
            logger.error("Failed to post all LDAP profiles. Trace: {}".format(format_exc()))
            raise e

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
