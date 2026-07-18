"""E-invoicing and e-way bill enums."""

from enum import StrEnum


class EInvoiceStatus(StrEnum):
    """Supported e-invoice lifecycle statuses."""

    GENERATED = "generated"
    CANCELLED = "cancelled"


class EWayBillStatus(StrEnum):
    """Supported e-way bill lifecycle statuses."""

    GENERATED = "generated"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class GSTProviderType(StrEnum):
    """Supported GST provider categories."""

    MOCK = "mock"
    GSP = "gsp"
    NIC = "nic"


class TransportMode(StrEnum):
    """Supported e-way bill transport modes."""

    ROAD = "road"
    RAIL = "rail"
    AIR = "air"
    SHIP = "ship"
