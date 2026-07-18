"""Ledger-specific exceptions."""

from app.common.exceptions import ConflictException, TaxPilotException


class LedgerAlreadyPostedException(ConflictException):
    """Raised when a journal has already been posted to the ledger."""

    error_code = "ledger.already_posted"


class LedgerInvalidJournalException(ConflictException):
    """Raised when a journal is not eligible for ledger posting."""

    error_code = "ledger.invalid_journal"


class LedgerPostingFailedException(TaxPilotException):
    """Raised when ledger posting cannot be completed."""

    error_code = "ledger.posting_failed"
