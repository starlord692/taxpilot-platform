"""Document automation exceptions."""

from app.common.exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)


class AutomationNotFoundException(NotFoundException):
    """Raised when automation state is not found."""

    error_code = "automation.not_found"


class AutomationValidationException(ValidationException):
    """Raised when a document cannot be automated."""

    error_code = "automation.validation_failed"


class AutomationConflictException(ConflictException):
    """Raised when automation conflicts with current state."""

    error_code = "automation.conflict"


class AutomationMappingException(ValidationException):
    """Raised when extracted fields cannot map to ERP requests."""

    error_code = "automation.mapping_failed"
