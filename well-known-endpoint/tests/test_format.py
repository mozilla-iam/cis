import json


class TestFormat(object):
    def test_json_format(self):
        json.load(open('tpl/mozilla-iam'))
        json.load(open('tpl/mozilla-iam-publisher-rules'))
