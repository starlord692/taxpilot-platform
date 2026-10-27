"""Catalog-specific exceptions."""

from app.common.exceptions import ConflictException, NotFoundException


class CatalogItemNotFoundException(NotFoundException):
    """Raised when a catalog item is not found."""

    error_code = "catalog.item_not_found"


class DuplicateCatalogItemException(ConflictException):
    """Raised when a catalog item code already exists for a business."""

    error_code = "catalog.duplicate_item"
