import os
from flask import Flask
from flask import jsonify
from json import loads
from cis_fake_well_known import well_known


app = Flask(__name__)


@app.route('/.well-known/mozilla-iam')
def mozilla_iam():
    return jsonify(well_known.MozillaIAM().data())


@app.route('/.well-known/mozilla-iam-publisher-rules')
def mozilla_iam_publisher_rules():
    fh = open(os.path.dirname(__file__) + '/json/rules.json')
    rules = loads(fh.read())
    fh.close()
    return jsonify(rules)
