
import os
from cis_identity_vault.models import user

from timeit import timeit


def wrapper(func, *args, **kwargs):
    def wrapped():
        return func(*args, **kwargs)
    return wrapped

class TestScanTiming(object):
    def setup(self):
        os.environ['CIS_ENVIRONMENT'] = 'testing'
        from cis_profile_retrieval_service.common import get_dynamodb_client
        from cis_profile_retrieval_service.common import get_table_resource
        self.dynamodb_client = get_dynamodb_client()
        self.dynamodb_table = get_table_resource()
    
    def test_timing_on_filtering(self):
        os.environ['CIS_ENVIRONMENT'] = 'testing'
        vault = user.Profile(self.dynamodb_table, self.dynamodb_client)
        wrapped_func = wrapper(vault.all_filtered, 'ad')
        assert timeit(wrapped_func) < 5.00