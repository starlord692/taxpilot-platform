"""Catalog exceptions."""

from app.common.exceptions import ConflictException, NotFoundException


class CatalogItemNotFoundException(NotFoundException):
    error_code = "catalog.item_not_found"


class DuplicateCatalogItemException(ConflictException):
    error_code = "catalog.duplicate_item"
