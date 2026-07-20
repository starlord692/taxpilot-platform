"""Catalog lifecycle events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class CatalogItemEvent(Event):
    catalog_item_id: uuid.UUID
    business_id: uuid.UUID
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class CatalogItemCreatedEvent(CatalogItemEvent):
    event_name: str = "catalog.item.created"


@dataclass(frozen=True)
class CatalogItemUpdatedEvent(CatalogItemEvent):
    event_name: str = "catalog.item.updated"


@dataclass(frozen=True)
class CatalogItemArchivedEvent(CatalogItemEvent):
    event_name: str = "catalog.item.archived"


@dataclass(frozen=True)
class CatalogItemRestoredEvent(CatalogItemEvent):
    event_name: str = "catalog.item.restored"
