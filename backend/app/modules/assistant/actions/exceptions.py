"""Assistant action exceptions."""

from app.common.exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)


class AssistantActionNotFoundException(NotFoundException):
    """Raised when an assistant action draft cannot be found."""

    error_code = "assistant.action_not_found"


class AssistantActionValidationException(ValidationException):
    """Raised when an assistant action draft is not valid."""

    error_code = "assistant.action_validation_failed"


class AssistantActionConflictException(ConflictException):
    """Raised when an assistant action conflicts with current state."""

    error_code = "assistant.action_conflict"
