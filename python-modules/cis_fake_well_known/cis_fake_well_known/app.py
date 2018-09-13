from flask import Flask
from flask import jsonify

from cis_fake_well_known import well_known


app = Flask(__name__)


@app.route('/.well-known/mozilla-iam')
def mozilla_iam():
    return jsonify(well_known.MozillIAM().data())
