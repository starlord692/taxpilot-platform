"""Sales-specific exceptions."""

from app.common.exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)


class SalesInvoiceNotFoundException(NotFoundException):
    """Raised when a sales invoice cannot be found."""

    error_code = "sales.invoice_not_found"


class SalesPaymentNotFoundException(NotFoundException):
    """Raised when a payment cannot be found."""

    error_code = "sales.payment_not_found"


class SalesCustomerNotFoundException(NotFoundException):
    """Raised when an invoice customer cannot be found."""

    error_code = "sales.customer_not_found"


class SalesDuplicateCustomerException(ConflictException):
    """Raised when a customer code or email already exists for a business."""

    error_code = "sales.duplicate_customer"


class SalesDuplicateInvoiceNumberException(ConflictException):
    """Raised when an invoice number already exists for a business."""

    error_code = "sales.duplicate_invoice_number"


class SalesInvalidInvoiceStatusException(ConflictException):
    """Raised when an invoice status transition is invalid."""

    error_code = "sales.invalid_invoice_status"


class SalesInvoiceValidationException(ValidationException):
    """Raised when invoice business validation fails."""

    error_code = "sales.invoice_validation_failed"


class SalesPaymentValidationException(ValidationException):
    """Raised when payment business validation fails."""

    error_code = "sales.payment_validation_failed"
