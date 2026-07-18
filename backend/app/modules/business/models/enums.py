"""Business model enums."""

from enum import StrEnum


class BusinessStatus(StrEnum):
    """Supported business lifecycle statuses."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class BusinessType(StrEnum):
    """Supported business organization types."""

    SOLE_PROPRIETOR = "sole_proprietor"
    PARTNERSHIP = "partnership"
    PRIVATE_LIMITED = "private_limited"
    LLP = "llp"
    FREELANCER = "freelancer"
    NON_PROFIT = "non_profit"


class RegistrationStatus(StrEnum):
    """Supported business registration statuses."""

    REGISTERED = "registered"
    UNREGISTERED = "unregistered"
    PENDING = "pending"
