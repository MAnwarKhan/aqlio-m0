"""Participant-safe application errors."""


class AqlioError(Exception):
    """Base error carrying participant-safe copy."""


class AuthorizationError(AqlioError):
    pass


class ValidationError(AqlioError):
    pass


class PreparationError(AqlioError):
    pass


class AllowanceExceeded(AqlioError):
    pass


class NotReadyError(AqlioError):
    pass


class ShareAccessError(AqlioError):
    pass


class RateLimitExceeded(AqlioError):
    pass
