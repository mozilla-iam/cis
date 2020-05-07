from cis_notifications.event import expired
import time


class TestExpiration(object):
    def test_expiration(self):
        ten_sec_ago = time.time() - 10.0
        assert expired(ten_sec_ago)

        one_day_ahead = time.time() + 24 * 60 * 60
        assert not expired(one_day_ahead, leeway=910)

        one_hour_ahead = time.time() + 60 * 60
        assert not expired(one_hour_ahead, leeway=910)

        now = time.time()
        assert expired(now, leeway=910)

        fifteen_min_ahead = time.time() + 900
        assert expired(fifteen_min_ahead, leeway=910)
