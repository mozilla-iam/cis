import json


class TestFormat(object):
    def test_json_format(self):
        json.load(open("tpl/dev.mozilla-iam"))
        json.load(open("tpl/prod.mozilla-iam"))
        json.load(open("tpl/mozilla-iam-publisher-rules"))
