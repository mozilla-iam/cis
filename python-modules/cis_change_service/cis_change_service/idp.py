import json
import logging

from functools import wraps
from flask import request
from flask import _request_ctx_stack
from six.moves.urllib.request import urlopen
from jose import jwt

from cis_change_service.common import get_config
from cis_change_service.exceptions import AuthError

logger = logging.getLogger(__name__)

CONFIG = get_config()

AUTH0_DOMAIN = CONFIG('auth0_domain', namespace='change_service', default='auth-dev.mozilla.auth0.com')
API_IDENTIFIER = CONFIG('api_identifier', namespace='change_service', default='https://change.sso.allizom.org')
ALGORITHMS = CONFIG('algorithms', namespace='change_service', default='RS256')


# Format error response and append status code
def get_token_auth_header():
    """Obtains the Access Token from the Authorization Header
    """
    auth = request.headers.get("Authorization", None)
    if not auth:
        raise AuthError({"code": "authorization_header_missing",
                        "description":
                            "Authorization header is expected"}, 401)

    parts = auth.split()

    if parts[0].lower() != "bearer":
        raise AuthError({"code": "invalid_header",
                        "description":
                            "Authorization header must start with"
                            " Bearer"}, 401)
    elif len(parts) == 1:
        raise AuthError({"code": "invalid_header",
                        "description": "Token not found"}, 401)
    elif len(parts) > 2:
        raise AuthError({"code": "invalid_header",
                        "description":
                            "Authorization header must be"
                            " Bearer token"}, 401)

    token = parts[1]
    return token


def get_jwks():
    # XXX TBD do this with request purely instead of six
    jsonurl = urlopen("https://" + AUTH0_DOMAIN + "/.well-known/jwks.json")
    jwks = json.loads(jsonurl.read())
    return jwks


def requires_auth(f):
    """Determines if the Access Token is valid
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        environment = CONFIG('environment', namespace='cis', default='local')
        jwt_validation = CONFIG('jwt_validation', namespace='cis', default='true')

        if environment == 'local' and jwt_validation == 'false':
            logger.debug('Local environment detected with auth bypass settings enabled.  Skipping JWT validation.')
            return f(*args, **kwargs)
        else:
            token = get_token_auth_header()
            jwks = get_jwks()
            unverified_header = jwt.get_unverified_header(token)
            rsa_key = {}
            for key in jwks["keys"]:
                if key["kid"] == unverified_header["kid"]:
                    rsa_key = {
                        "kty": key["kty"],
                        "kid": key["kid"],
                        "use": key["use"],
                        "n": key["n"],
                        "e": key["e"]
                    }
            if rsa_key:
                try:
                    logger.debug(token)
                    payload = jwt.decode(
                        token,
                        rsa_key,
                        algorithms=ALGORITHMS,
                        audience=API_IDENTIFIER,
                        issuer="https://" + AUTH0_DOMAIN + "/"
                    )
                except jwt.ExpiredSignatureError as e:
                    logger.error(e)
                    raise AuthError({"code": "token_expired",
                                    "description": "token is expired"}, 401)
                except jwt.JWTClaimsError as e:
                    logger.error(e)
                    raise AuthError({"code": "invalid_claims",
                                    "description":
                                        "incorrect claims,"
                                        "please check the audience and issuer"}, 401)
                except Exception as e:
                    logger.error(e)
                    raise AuthError({"code": "invalid_header",
                                    "description":
                                        "Unable to parse authentication"
                                        " token."}, 401)

                _request_ctx_stack.top.current_user = payload
                return f(*args, **kwargs)
            raise AuthError({"code": "invalid_header",
                            "description": "Unable to find appropriate key"}, 401)
    return decorated


def requires_scope(required_scope):
    """Determines if the required scope is present in the Access Token
    Args:
        required_scope (str): The scope required to access the resource
    """
    token = get_token_auth_header()
    unverified_claims = jwt.get_unverified_claims(token)
    if unverified_claims.get("scope"):
            token_scopes = unverified_claims["scope"].split()
            for token_scope in token_scopes:
                if token_scope == required_scope:
                    return True
    return False
