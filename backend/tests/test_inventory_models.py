"""Tests for Inventory Management database model mappings."""

import uuid
from collections.abc import Iterable
from decimal import Decimal
from typing import cast

from sqlalchemy import Table, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, RelationshipProperty, configure_mappers

import app.modules.business.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
from app.modules.inventory.models import (
    MovementType,
    Product,
    StockBalance,
    StockMovement,
    Warehouse,
)


def unique_constraint_sets(model: type[DeclarativeBase]) -> set[tuple[str, ...]]:
    """Return multi-column unique constraint column names for a mapped model."""
    table = cast(Table, model.__table__)
    constraints: Iterable[UniqueConstraint] = (
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    )
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in constraints
    }


def test_product_creation() -> None:
    """Product can be constructed with expected fields and defaults."""
    business_id = uuid.uuid4()
    product = Product(
        business_id=business_id,
        sku="LAPTOP-001",
        name="Business Laptop",
        description="14 inch laptop",
        category="Hardware",
        unit_of_measure="pcs",
        barcode="8900000000012",
        purchase_price=Decimal("50000.00"),
        selling_price=Decimal("65000.00"),
        reorder_level=Decimal("5.0000"),
    )

    assert product.business_id == business_id
    assert product.sku == "LAPTOP-001"
    assert product.name == "Business Laptop"
    assert product.category == "Hardware"
    assert product.unit_of_measure == "pcs"
    assert product.purchase_price == Decimal("50000.00")
    assert Product.__table__.c.is_active.default is not None
    assert Product.__table__.c.is_active.default.arg is True


def test_warehouse_creation() -> None:
    """Warehouse can be constructed with expected fields and defaults."""
    business_id = uuid.uuid4()
    warehouse = Warehouse(
        business_id=business_id,
        code="MAIN",
        name="Main Warehouse",
        address="Bengaluru",
    )

    assert warehouse.business_id == business_id
    assert warehouse.code == "MAIN"
    assert warehouse.name == "Main Warehouse"
    assert Warehouse.__table__.c.is_default.default is not None
    assert Warehouse.__table__.c.is_default.default.arg is False
    assert Warehouse.__table__.c.is_active.default is not None
    assert Warehouse.__table__.c.is_active.default.arg is True


def test_stock_balance_creation() -> None:
    """Stock balance tracks quantities for one product and warehouse."""
    product_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    balance = StockBalance(
        business_id=uuid.uuid4(),
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity_on_hand=Decimal("25.0000"),
        quantity_reserved=Decimal("5.0000"),
        quantity_available=Decimal("20.0000"),
    )

    assert balance.product_id == product_id
    assert balance.warehouse_id == warehouse_id
    assert balance.quantity_on_hand == Decimal("25.0000")
    assert balance.quantity_reserved == Decimal("5.0000")
    assert balance.quantity_available == Decimal("20.0000")
    assert StockBalance.__table__.c.last_updated.default is not None


def test_stock_movement_creation() -> None:
    """Stock movement records source reference details."""
    reference_id = uuid.uuid4()
    movement = StockMovement(
        business_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        warehouse_id=uuid.uuid4(),
        movement_type=MovementType.PURCHASE,
        quantity=Decimal("10.0000"),
        reference_type="purchase_invoice",
        reference_id=reference_id,
        notes="Initial purchase receipt",
    )

    assert movement.movement_type == MovementType.PURCHASE
    assert movement.quantity == Decimal("10.0000")
    assert movement.reference_type == "purchase_invoice"
    assert movement.reference_id == reference_id
    assert movement.notes == "Initial purchase receipt"


def test_inventory_relationships() -> None:
    """Inventory models expose expected ownership relationships."""
    configure_mappers()

    product_balances = Product.__mapper__.relationships["stock_balances"]
    warehouse_balances = Warehouse.__mapper__.relationships["stock_balances"]
    balance_product = StockBalance.__mapper__.relationships["product"]
    balance_warehouse = StockBalance.__mapper__.relationships["warehouse"]
    product_movements = Product.__mapper__.relationships["stock_movements"]
    warehouse_movements = Warehouse.__mapper__.relationships["stock_movements"]
    movement_product = StockMovement.__mapper__.relationships["product"]
    movement_warehouse = StockMovement.__mapper__.relationships["warehouse"]

    assert isinstance(product_balances, RelationshipProperty)
    assert isinstance(warehouse_balances, RelationshipProperty)
    assert isinstance(balance_product, RelationshipProperty)
    assert isinstance(balance_warehouse, RelationshipProperty)
    assert isinstance(product_movements, RelationshipProperty)
    assert isinstance(warehouse_movements, RelationshipProperty)
    assert isinstance(movement_product, RelationshipProperty)
    assert isinstance(movement_warehouse, RelationshipProperty)
    assert product_balances.uselist is True
    assert warehouse_balances.uselist is True
    assert balance_product.uselist is False
    assert balance_warehouse.uselist is False
    assert product_movements.uselist is True
    assert warehouse_movements.uselist is True
    assert movement_product.uselist is False
    assert movement_warehouse.uselist is False


def test_inventory_uniqueness_rules() -> None:
    """Inventory models define required business-scoped uniqueness."""
    assert ("business_id", "sku") in unique_constraint_sets(Product)
    assert ("business_id", "code") in unique_constraint_sets(Warehouse)
    assert (
        "product_id",
        "warehouse_id",
    ) in unique_constraint_sets(StockBalance)


def test_movement_type_enum_values() -> None:
    """Movement enum exposes expected stock movement values."""
    assert MovementType.PURCHASE.value == "purchase"
    assert MovementType.SALE.value == "sale"
    assert MovementType.ADJUSTMENT.value == "adjustment"
    assert MovementType.RETURN.value == "return"
    assert MovementType.TRANSFER.value == "transfer"
