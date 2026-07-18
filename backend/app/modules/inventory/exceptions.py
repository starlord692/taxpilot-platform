"""Inventory Management-specific exceptions."""

from app.common.exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)


class ProductNotFoundException(NotFoundException):
    """Raised when a product cannot be found."""

    error_code = "inventory.product_not_found"


class WarehouseNotFoundException(NotFoundException):
    """Raised when a warehouse cannot be found."""

    error_code = "inventory.warehouse_not_found"


class StockBalanceNotFoundException(NotFoundException):
    """Raised when a stock balance cannot be found."""

    error_code = "inventory.stock_balance_not_found"


class DuplicateProductException(ConflictException):
    """Raised when product uniqueness rules are violated."""

    error_code = "inventory.duplicate_product"


class DuplicateWarehouseException(ConflictException):
    """Raised when warehouse uniqueness rules are violated."""

    error_code = "inventory.duplicate_warehouse"


class ProductInactiveException(ConflictException):
    """Raised when a product is already inactive."""

    error_code = "inventory.product_inactive"


class ProductActiveException(ConflictException):
    """Raised when a product is already active."""

    error_code = "inventory.product_active"


class WarehouseInactiveException(ConflictException):
    """Raised when a warehouse is already inactive."""

    error_code = "inventory.warehouse_inactive"


class WarehouseActiveException(ConflictException):
    """Raised when a warehouse is already active."""

    error_code = "inventory.warehouse_active"


class ActiveStockExistsException(ConflictException):
    """Raised when deactivation is blocked by active stock."""

    error_code = "inventory.active_stock_exists"


class DefaultWarehouseException(ConflictException):
    """Raised when default warehouse rules are violated."""

    error_code = "inventory.default_warehouse_conflict"


class InventoryValidationException(ValidationException):
    """Raised when an inventory movement request is invalid."""

    error_code = "inventory.validation_failed"


class NegativeStockException(ConflictException):
    """Raised when a stock operation would create negative availability."""

    error_code = "inventory.negative_stock"
