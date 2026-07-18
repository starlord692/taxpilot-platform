"""Document extraction exceptions."""

from app.common.exceptions import NotFoundException, ValidationException


class ExtractionNotFoundException(NotFoundException):
    """Raised when extracted document output cannot be found."""

    error_code = "document.extraction_not_found"


class ExtractionValidationException(ValidationException):
    """Raised when extraction cannot be performed or validated."""

    error_code = "document.extraction_validation_failed"


class ExtractionFailedException(ValidationException):
    """Raised when extraction processing fails."""

    error_code = "document.extraction_failed"
