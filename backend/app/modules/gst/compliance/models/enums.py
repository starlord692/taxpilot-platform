"""GST compliance enums."""

from enum import StrEnum


class GSTFilingFrequency(StrEnum):
    """Supported GST filing frequencies."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class GSTReturnStatus(StrEnum):
    """GST return period lifecycle status."""

    GENERATED = "generated"
    FILED = "filed"
