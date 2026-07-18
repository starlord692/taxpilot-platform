"""E-invoicing exception hierarchy."""

from app.common.exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)


class EInvoiceNotFoundException(NotFoundException):
    """Raised when e-invoice data is not found."""

    error_code = "einvoice.not_found"


class EWayBillNotFoundException(NotFoundException):
    """Raised when e-way bill data is not found."""

    error_code = "ewaybill.not_found"


class GSTProviderFailureException(ValidationException):
    """Raised when a provider operation fails."""

    error_code = "einvoice.provider_failure"


class EInvoiceValidationException(ValidationException):
    """Raised when e-invoice validation fails."""

    error_code = "einvoice.validation_failed"


class DuplicateIRNException(ConflictException):
    """Raised when an invoice already has an active IRN."""

    error_code = "einvoice.duplicate_irn"


class DuplicateEWayBillException(ConflictException):
    """Raised when an invoice already has an active e-way bill."""

    error_code = "ewaybill.duplicate"
