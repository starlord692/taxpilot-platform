"""Document review exceptions."""

from app.common.exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)


class DocumentReviewNotFoundException(NotFoundException):
    """Raised when review data is not found."""

    error_code = "document.review_not_found"


class DocumentReviewValidationException(ValidationException):
    """Raised when validation or review cannot proceed."""

    error_code = "document.review_validation_failed"


class DocumentReviewConflictException(ConflictException):
    """Raised when review state conflicts with requested operation."""

    error_code = "document.review_conflict"
