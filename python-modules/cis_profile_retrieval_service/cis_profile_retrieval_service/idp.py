import logging
import requests

from functools import wraps
from flask import request
from flask import _request_ctx_stack
from jose import jwt

from cis_profile_retrieval_service.common import get_config
from cis_profile_retrieval_service.exceptions import AuthError

logger = logging.getLogger(__name__)

CONFIG = get_config()

AUTH0_DOMAIN = CONFIG("auth0_domain", namespace="person_api", default="auth-dev.mozilla.auth0.com")
API_IDENTIFIER = CONFIG("api_identifier", namespace="person_api", default="api.dev.sso.allizom.org")
ALGORITHMS = CONFIG("algorithms", namespace="change_service", default="RS256")


# Format error response and append status code
def get_token_auth_header():
    """Obtains the Access Token from the Authorization Header"""
    auth = request.headers.get("Authorization", None)
    if not auth:
        raise AuthError(
            {"code": "authorization_header_missing", "description": "Authorization header is expected"}, 401
        )

    parts = auth.split()

    if parts[0].lower() != "bearer":
        raise AuthError(
            {"code": "invalid_header", "description": "Authorization header must start with" " Bearer"}, 401
        )
    elif len(parts) == 1:
        raise AuthError({"code": "invalid_header", "description": "Token not found"}, 401)
    elif len(parts) > 2:
        raise AuthError({"code": "invalid_header", "description": "Authorization header must be" " Bearer token"}, 401)

    token = parts[1]
    return token


def get_jwks():
    return requests.get(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json").json()


def requires_auth(f):
    """Determines if the Access Token is valid"""

    @wraps(f)
    def decorated(*args, **kwargs):
        environment = CONFIG("environment", namespace="person_api", default="local")
        jwt_validation = CONFIG("jwt_validation", namespace="person_api", default="true")

        if environment == "local" and jwt_validation == "false":
            logger.debug(
                "Local environment detected with auth bypass settings enabled.  Skipping JWT validation.",
                extra={"jwt_validation": False},
            )
            return f(*args, **kwargs)
        else:
            token = get_token_auth_header()
            jwks = get_jwks()
            unverified_header = jwt.get_unverified_header(token)
            rsa_key = {}
            for key in jwks["keys"]:
                if key["kid"] == unverified_header["kid"]:
                    rsa_key = {"kty": key["kty"], "kid": key["kid"], "use": key["use"], "n": key["n"], "e": key["e"]}
            if rsa_key:
                try:
                    logger.debug(token)
                    payload = jwt.decode(
                        token,
                        rsa_key,
                        algorithms=ALGORITHMS,
                        audience=API_IDENTIFIER,
                        issuer="https://" + AUTH0_DOMAIN + "/",
                    )
                    logger.debug("An auth token has been recieved and verified.", extra={"code": 200})
                except jwt.ExpiredSignatureError as e:
                    logger.error("The jwt received has an expired timestamp.", extra={"code": 401, "error": e})
                    raise AuthError({"code": "token_expired", "description": "token is expired"}, 401)
                except jwt.JWTClaimsError as e:
                    logger.error("The jwt received has invalid claims.", extra={"code": 401, "error": e})
                    raise AuthError(
                        {
                            "code": "invalid_claims",
                            "description": "incorrect claims," "please check the audience and issuer",
                        },
                        401,
                    )
                except Exception as e:
                    logger.error("The jwt received has an unhandled exception.", extra={"code": 401, "error": e})
                    raise AuthError(
                        {"code": "invalid_header", "description": "Unable to parse authentication" " token."}, 401
                    )

                _request_ctx_stack.top.current_user = payload
                return f(*args, **kwargs)
            raise AuthError({"code": "invalid_header", "description": "Unable to find appropriate key"}, 401)

    return decorated


def get_scopes(token):
    """Takes in a bearer token and deserializes it to parse out the scopes.

    Arguments:
        token {[string]} -- A bearer token issued by our token vending machine.  In this case auth zero.

    Returns:
        [list] -- a list of scopes.
    """

    try:
        split_bearer = token.split()
        unverified_claims = jwt.get_unverified_claims(split_bearer[1])
    except AttributeError:
        logger.warning("Could not parse bearer token, this client will have empty scopes")
        unverified_claims = {}

    if unverified_claims.get("scope"):
        token_scopes = unverified_claims["scope"].split()
        logger.debug("Returning the following token scopes: {}".format(token_scopes))
        return token_scopes
    else:
        logger.debug("No scopes in token returning empty list.")
        return []
