import boto3
import common
import json
import lzma

from logging import getLogger


logger = getLogger(__name__)


class User(object):
    """Retrieve the ldap users from the ldap.xz.json and process."""
    def __init__(self):
        self.s3 = None
        self.ldap_json = None

    def _connect_s3(self):
        if self.s3 is None:
            self.s3 = boto3.resource('s3')

    def _get_ldap_json(self):
        self._connect_s3()
        obj = self.s3.Object(
            common.S3_BUCKET_NAME,
            common.LDAP_JSON_FILE
        )

        tarred_json = bytes(obj.get()["Body"].read())
        ldap_json = json.loads(lzma.decompress(tarred_json))
        self.ldap_json = ldap_json

    @property
    def all(self):
        if self.ldap_json is None:
            self._get_ldap_json()

        return self.ldap_json
