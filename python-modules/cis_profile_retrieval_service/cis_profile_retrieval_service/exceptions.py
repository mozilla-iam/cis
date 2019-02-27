# Error handler
class AuthError(Exception):
    def __init__(self, error, status_code):
        logger.error(
            "Authentication failed for the caller.",
            extra={
                'error': error,
                'status_code': status_code
            }
        )
        self.error = error
        self.status_code = status_code
