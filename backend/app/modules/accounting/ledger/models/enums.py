"""General Ledger enum definitions."""

from enum import StrEnum


class LedgerEntryType(StrEnum):
    """Supported ledger entry sides."""

    DEBIT = "debit"
    CREDIT = "credit"
