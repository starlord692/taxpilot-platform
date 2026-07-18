"""Chart of accounts model enums."""

from enum import StrEnum


class NormalBalance(StrEnum):
    """Supported normal balance directions for accounts."""

    DEBIT = "debit"
    CREDIT = "credit"
