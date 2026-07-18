"""Expense Management enumerations."""

from enum import StrEnum


class ExpenseStatus(StrEnum):
    """Expense lifecycle status."""

    DRAFT = "draft"
    APPROVED = "approved"
    PAID = "paid"
    CANCELLED = "cancelled"


class ExpenseCategory(StrEnum):
    """Supported expense categories."""

    TRAVEL = "travel"
    OFFICE = "office"
    RENT = "rent"
    UTILITIES = "utilities"
    MARKETING = "marketing"
    SALARY = "salary"
    PROFESSIONAL_FEES = "professional_fees"
    SOFTWARE = "software"
    HARDWARE = "hardware"
    OTHER = "other"
