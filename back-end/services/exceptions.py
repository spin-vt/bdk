"""Domain errors raised by the service layer.

A service raises ServiceError(message, status) for an expected, user-facing
failure (bad input, authorization, not found). Handlers catch it and render it
in their existing response shape — keeping the current frontend contract intact
(the full error-shape unification is deferred). Unexpected errors are NOT
wrapped; they propagate so the handler's existing catch-all (or Flask) handles
them exactly as before.
"""


class ServiceError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status
