"""Journal model enums."""

from enum import StrEnum


class JournalStatus(StrEnum):
    """Supported journal entry statuses."""

    DRAFT = "draft"
    POSTED = "posted"
    REVERSED = "reversed"
