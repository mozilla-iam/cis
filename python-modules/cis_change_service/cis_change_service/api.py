import json
import logging

from aws_xray_sdk.ext.flask.middleware import XRayMiddleware
from aws_xray_sdk.core import xray_recorder

from flask import Flask
from flask import jsonify
from flask import request
from flask_cors import CORS
from flask_cors import cross_origin
from cis_aws import connect
from cis_change_service.common import get_config
from cis_change_service import profile
from cis_change_service.exceptions import IntegrationError
from cis_change_service.exceptions import VerificationError
from cis_change_service.idp import requires_auth
from cis_change_service.idp import requires_scope
from cis_change_service.idp import AuthError
from cis_change_service import __version__


app = Flask(__name__)
config = get_config()
logger = logging.getLogger(__name__)


cis_environment = config("environment", namespace="cis")
# Configure the X-Ray recorder to generate segments with our service name
xray_recorder.configure(service="{}_profile_retrieval_service".format(cis_environment))

# Instrument the Flask application
XRayMiddleware(app, xray_recorder)


CORS(
    app,
    allow_headers=(
        "x-requested-with",
        "content-type",
        "accept",
        "origin",
        "authorization",
        "x-csrftoken",
        "withcredentials",
        "cache-control",
        "cookie",
        "session-id",
    ),
    supports_credentials=True,
)


@app.errorhandler(AuthError)
def handle_auth_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response


@app.errorhandler(VerificationError)
def handle_verification_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response


@app.errorhandler(IntegrationError)
def handle_integration_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response


@app.route("/v2")
def index():
    return "Mozilla Change Integration Service Endpoint"


@app.route("/v2/version")
def version():
    response = __version__
    return jsonify(message=response)


@app.route("/v2/user", methods=["GET", "POST", "PUT", "DELETE"])
@cross_origin(headers=["Content-Type", "Authorization"])
@requires_auth
@requires_scope("write")
def change():
    connection = connect.AWS()
    connection.session()
    identity_vault_client = connection.identity_vault_client()

    user_profile = request.get_json(silent=True)
    if isinstance(user_profile, str):
        user_profile = json.loads(user_profile)

    user_id = request.args.get("user_id", user_profile["user_id"]["value"])
    logger.info("A json payload was received for user: {}".format(user_id), extra={"user_id": user_id})
    vault = profile.Vault(sequence_number=None, profile_json=user_profile, **request.args)

    if request.method in ["POST", "PUT", "GET"]:
        vault.identity_vault_client = identity_vault_client
        result = vault.put_profile(user_profile)
        logger.info(
            "The result of publishing for user: {} is: {}".format(user_id, result),
            extra={"user_id": user_id, "result": result},
        )
    if config("allow_delete", namespace="cis", default="false") == "true":
        if request.method in ["DELETE"]:
            vault.identity_vault_client = identity_vault_client
            result = vault.delete_profile(user_profile)
            logger.info(
                "A delete operation was performed for user: {}".format(user_id),
                extra={"user_id": user_id, "result": result},
            )
    return jsonify(result)


@app.route("/v2/users", methods=["GET", "POST", "PUT"])
@cross_origin(headers=["Content-Type", "Authorization"])
@requires_auth
@requires_scope("write")
def changes():
    connection = connect.AWS()
    connection.session()
    identity_vault_client = connection.identity_vault_client()
    profiles = request.get_json(silent=True)
    logger.info("A list numbering: {} profiles has been received.".format(len(profiles)))
    vault = profile.Vault(sequence_number=None)
    vault.identity_vault_client = identity_vault_client
    results = vault.put_profiles(profiles)
    logger.info("The result of the attempt to publish the profiles was: {}".format(results), extra={"results": results})
    return jsonify(results)


@app.route("/v2/status", methods=["GET"])
@cross_origin(headers=["Content-Type", "Authorization"])
@requires_scope("write")
def status():
    sequence_number = request.args.get("sequenceNumber")
    status = profile.Status(sequence_number)
    result = status.all
    return jsonify(result)
