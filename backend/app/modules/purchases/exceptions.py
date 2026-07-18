"""Purchase Management-specific exceptions."""

from app.common.exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)


class SupplierNotFoundException(NotFoundException):
    """Raised when a supplier cannot be found."""

    error_code = "purchases.supplier_not_found"


class DuplicateSupplierCodeException(ConflictException):
    """Raised when a supplier code already exists for a business."""

    error_code = "purchases.duplicate_supplier_code"


class DuplicateSupplierException(ConflictException):
    """Raised when supplier uniqueness rules are violated."""

    error_code = "purchases.duplicate_supplier"


class SupplierInactiveException(ConflictException):
    """Raised when a supplier is inactive for a requested operation."""

    error_code = "purchases.supplier_inactive"


class SupplierHasOpenPurchasesException(ConflictException):
    """Raised when supplier deactivation is blocked by unpaid purchases."""

    error_code = "purchases.supplier_has_open_purchases"


class PurchaseNotFoundException(NotFoundException):
    """Raised when a purchase invoice cannot be found."""

    error_code = "purchases.purchase_not_found"


class DuplicatePurchaseNumberException(ConflictException):
    """Raised when a purchase number already exists for a business."""

    error_code = "purchases.duplicate_purchase_number"


class DuplicatePurchaseInvoiceException(ConflictException):
    """Raised when supplier invoice uniqueness rules are violated."""

    error_code = "purchases.duplicate_invoice_number"


class InvalidPurchaseStatusException(ConflictException):
    """Raised when a purchase status transition is invalid."""

    error_code = "purchases.invalid_purchase_status"


class PurchaseValidationException(ValidationException):
    """Raised when purchase business validation fails."""

    error_code = "purchases.validation_failed"
