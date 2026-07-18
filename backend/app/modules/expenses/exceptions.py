"""Expense Management-specific exceptions."""

from app.common.exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)


class VendorNotFoundException(NotFoundException):
    """Raised when a vendor cannot be found."""

    error_code = "expenses.vendor_not_found"


class DuplicateVendorCodeException(ConflictException):
    """Raised when a vendor code already exists for a business."""

    error_code = "expenses.duplicate_vendor_code"


class VendorInactiveException(ConflictException):
    """Raised when a vendor is inactive for a requested operation."""

    error_code = "expenses.vendor_inactive"


class ExpenseNotFoundException(NotFoundException):
    """Raised when an expense cannot be found."""

    error_code = "expenses.expense_not_found"


class DuplicateExpenseNumberException(ConflictException):
    """Raised when an expense number already exists for a business."""

    error_code = "expenses.duplicate_expense_number"


class InvalidExpenseStatusException(ConflictException):
    """Raised when an expense status transition is invalid."""

    error_code = "expenses.invalid_expense_status"


class ExpenseValidationException(ValidationException):
    """Raised when expense business validation fails."""

    error_code = "expenses.validation_failed"
