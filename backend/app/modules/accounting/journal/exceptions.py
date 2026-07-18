"""Journal-specific exceptions."""

from http import HTTPStatus

from app.common.exceptions import (
    ConflictException,
    NotFoundException,
    TaxPilotException,
)


class JournalNotFoundException(NotFoundException):
    """Raised when a journal entry cannot be found."""

    error_code = "journal.not_found"


class JournalUnbalancedException(ConflictException):
    """Raised when journal entry debits and credits do not balance."""

    error_code = "journal.unbalanced"


class JournalInvalidStatusException(ConflictException):
    """Raised when a journal entry has an invalid lifecycle status."""

    error_code = "journal.invalid_status"


class JournalAccountInactiveException(ConflictException):
    """Raised when a journal line references an inactive account."""

    error_code = "journal.account_inactive"


class JournalValidationFailedException(TaxPilotException):
    """Raised when a journal entry fails posting validation."""

    status_code = HTTPStatus.BAD_REQUEST
    error_code = "journal.validation_failed"
