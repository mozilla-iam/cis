

class CISError(Exception):
    """Base error class."""
    pass


class AuthZeroUnavailable(CISExceptions):
    """
    Raised when the auth0 API fails to return a token.
    """
    def __init__(self):
        msg = "The identity provider failed to return a bearer token."
        CISError.__init__(self, msg)
