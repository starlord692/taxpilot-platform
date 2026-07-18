"""Inventory Management enumerations."""

from enum import StrEnum


class MovementType(StrEnum):
    """Stock movement source type."""

    PURCHASE = "purchase"
    SALE = "sale"
    ADJUSTMENT = "adjustment"
    RETURN = "return"
    TRANSFER = "transfer"
