"""Catalog enumerations."""

from enum import StrEnum


class ItemType(StrEnum):
    PRODUCT = "product"
    SERVICE = "service"


class CatalogItemStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
