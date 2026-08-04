"""Business Brief boundary exceptions."""


class BusinessBriefAccessDeniedError(PermissionError):
    """Raised when a user is not authorized for the requested business context."""


class BusinessBriefSourceMismatchError(ValueError):
    """Raised when an authoritative input does not match the requested context."""
