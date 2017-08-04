import unittest

class UtilsTest(unittest.TestCase):
    def test_stream_logger_init(self):
        from cis.libs import utils

        u = utils.StructuredLogger('foo', 2)
        assert u is not None

    def test_stream_logger_init(self):
        from cis.libs import utils

        u = utils.StructuredLogger('foo', 2)

        logger = u.get_logger()
        assert logger is None