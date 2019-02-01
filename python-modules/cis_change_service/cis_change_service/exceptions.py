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
