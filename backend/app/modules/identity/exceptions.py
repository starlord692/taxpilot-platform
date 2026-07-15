"""Identity-specific exceptions."""

from app.common.exceptions import ConflictException


class IdentityEmailAlreadyExistsException(ConflictException):
    """Raised when an identity email address already exists."""

    error_code = "identity.email_already_exists"
