"""Sales model enums."""

from enum import StrEnum


class InvoiceStatus(StrEnum):
    """Supported sales invoice lifecycle statuses."""

    DRAFT = "draft"
    ISSUED = "issued"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"


class PaymentMethod(StrEnum):
    """Supported invoice payment methods."""

    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    UPI = "upi"
    CARD = "card"
    CHEQUE = "cheque"
    OTHER = "other"
