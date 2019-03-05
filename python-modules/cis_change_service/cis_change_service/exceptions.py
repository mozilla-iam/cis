# Error handler
class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


class VerificationError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


class IntegrationError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


class AttributeMismatch(Exception):
    """Raised in profile lib if the args do not match the json structure passed in."""

    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code
