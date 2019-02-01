import logging
import socket

import cis_logger


class TestLogger(object):
    def setup_class(self):
        self.logger = logging.getLogger()

        handler = logging.StreamHandler()
        handler.setFormatter(cis_logger.JsonFormatter(extra={"hello": "world", "hostname": socket.gethostname()}))

        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def test_logger(self):
        test_logger = logging.getLogger("test")
        test_logger.info({"special": "value", "run": 12})
        test_logger.info("classic message", extra={"special": "value", "run": 12})

    def test_an_exception(self):
        test_logger = logging.getLogger("test")

        try:
            raise Exception("test")
        except Exception:
            test_logger.exception("This is a fake exception")
