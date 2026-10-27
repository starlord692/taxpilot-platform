"""Catalog enumerations."""

from enum import StrEnum


class ItemType(StrEnum):
    """Catalog item classification."""

    PRODUCT = "product"
    SERVICE = "service"


class CatalogItemStatus(StrEnum):
    """Catalog item lifecycle status."""

    ACTIVE = "active"
    ARCHIVED = "archived"
