"""GST configuration enums."""

from enum import StrEnum


class GSTRegistrationType(StrEnum):
    """Supported GST registration types."""

    REGULAR = "regular"
    COMPOSITION = "composition"
    CASUAL = "casual"
    NON_RESIDENT = "non_resident"


class GSTTaxMode(StrEnum):
    """Supported default GST tax modes."""

    INTRA_STATE = "intra_state"
    INTER_STATE = "inter_state"


class GSTRoundingMethod(StrEnum):
    """Supported GST rounding methods."""

    NEAREST = "nearest"
    UP = "up"
    DOWN = "down"
