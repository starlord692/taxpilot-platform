"""Identity model enums."""

from enum import StrEnum


class UserStatus(StrEnum):
    """Supported identity user lifecycle statuses."""

    PENDING = "pending"
    ACTIVE = "active"
    DISABLED = "disabled"
    LOCKED = "locked"
