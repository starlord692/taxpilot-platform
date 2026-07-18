"""Inventory lifecycle events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class ProductCreatedEvent(Event):
    """Event published after a product is created."""

    product_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "inventory.product.created"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class ProductUpdatedEvent(Event):
    """Event published after a product is updated."""

    product_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "inventory.product.updated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class ProductActivatedEvent(Event):
    """Event published after a product is activated."""

    product_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "inventory.product.activated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class ProductDeactivatedEvent(Event):
    """Event published after a product is deactivated."""

    product_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "inventory.product.deactivated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class WarehouseCreatedEvent(Event):
    """Event published after a warehouse is created."""

    warehouse_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "inventory.warehouse.created"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class WarehouseUpdatedEvent(Event):
    """Event published after a warehouse is updated."""

    warehouse_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "inventory.warehouse.updated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class WarehouseActivatedEvent(Event):
    """Event published after a warehouse is activated."""

    warehouse_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "inventory.warehouse.activated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class WarehouseDeactivatedEvent(Event):
    """Event published after a warehouse is deactivated."""

    warehouse_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "inventory.warehouse.deactivated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class StockReceivedEvent(Event):
    """Event published after stock is received from a purchase."""

    business_id: uuid.UUID
    source_id: uuid.UUID
    movement_ids: tuple[uuid.UUID, ...]
    event_name: str = "inventory.stock.received"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class StockIssuedEvent(Event):
    """Event published after stock is issued for a sale."""

    business_id: uuid.UUID
    source_id: uuid.UUID
    movement_ids: tuple[uuid.UUID, ...]
    event_name: str = "inventory.stock.issued"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class StockAdjustedEvent(Event):
    """Event published after stock is adjusted."""

    business_id: uuid.UUID
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    movement_id: uuid.UUID
    event_name: str = "inventory.stock.adjusted"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class StockTransferredEvent(Event):
    """Event published after stock is transferred between warehouses."""

    business_id: uuid.UUID
    product_id: uuid.UUID
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    movement_ids: tuple[uuid.UUID, ...]
    event_name: str = "inventory.stock.transferred"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class StockReservedEvent(Event):
    """Event published after stock is reserved."""

    business_id: uuid.UUID
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    quantity: Decimal
    reference_id: uuid.UUID | None = None
    event_name: str = "inventory.stock.reserved"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class StockReleasedEvent(Event):
    """Event published after a stock reservation is released."""

    business_id: uuid.UUID
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    quantity: Decimal
    reference_id: uuid.UUID | None = None
    event_name: str = "inventory.stock.released"
    occurred_at: datetime = field(default_factory=utc_now)
