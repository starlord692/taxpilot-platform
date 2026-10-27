"""Catalog lifecycle events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class CatalogItemEvent(Event):
    """Base catalog item domain event."""

    catalog_item_id: uuid.UUID
    business_id: uuid.UUID
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class CatalogItemCreatedEvent(CatalogItemEvent):
    """Event emitted when a catalog item is created."""

    event_name: str = "catalog.item.created"


@dataclass(frozen=True)
class CatalogItemUpdatedEvent(CatalogItemEvent):
    """Event emitted when a catalog item is updated."""

    event_name: str = "catalog.item.updated"


@dataclass(frozen=True)
class CatalogItemArchivedEvent(CatalogItemEvent):
    """Event emitted when a catalog item is archived."""

    event_name: str = "catalog.item.archived"


@dataclass(frozen=True)
class CatalogItemRestoredEvent(CatalogItemEvent):
    """Event emitted when a catalog item is restored."""

    event_name: str = "catalog.item.restored"
