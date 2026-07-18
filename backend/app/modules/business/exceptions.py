"""Business-specific exceptions."""

from http import HTTPStatus

from app.common.exceptions import (
    ConflictException,
    NotFoundException,
    TaxPilotException,
)


class BusinessNotFoundException(NotFoundException):
    """Raised when a business cannot be found."""

    error_code = "business.not_found"


class BusinessDuplicateNameException(ConflictException):
    """Raised when a business legal name already exists."""

    error_code = "business.duplicate_name"


class BusinessArchivedException(ConflictException):
    """Raised when an archived business cannot be modified."""

    error_code = "business.archived"


class BusinessNotMemberException(TaxPilotException):
    """Raised when a user is not a member of a business."""

    status_code = HTTPStatus.FORBIDDEN
    error_code = "business.not_member"
