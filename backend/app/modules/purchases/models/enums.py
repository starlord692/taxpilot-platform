"""Purchase Management enumerations."""

from enum import StrEnum


class PurchaseStatus(StrEnum):
    """Purchase invoice lifecycle status."""

    DRAFT = "draft"
    APPROVED = "approved"
    RECEIVED = "received"
    PAID = "paid"
    CANCELLED = "cancelled"
