"""Tests for Inventory Management Pydantic schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

import app.modules.business.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
from app.modules.inventory.models import (
    MovementType,
    Product,
    StockBalance,
    StockMovement,
    Warehouse,
)
from app.modules.inventory.schemas import (
    ProductCreate,
    ProductResponse,
    StockBalanceResponse,
    StockMovementCreate,
    StockMovementResponse,
    WarehouseCreate,
    WarehouseResponse,
)


def build_product_payload() -> dict[str, object]:
    """Build a valid product create payload."""
    return {
        "sku": "  LAPTOP-001  ",
        "name": "  Business   Laptop  ",
        "description": "14 inch laptop",
        "category": "Hardware",
        "unit_of_measure": "pcs",
        "barcode": "8900000000012",
        "purchase_price": "50000.00",
        "selling_price": "65000.00",
        "reorder_level": "5.0000",
        "is_active": True,
    }


def build_warehouse_payload() -> dict[str, object]:
    """Build a valid warehouse create payload."""
    return {
        "code": "  MAIN  ",
        "name": "  Main   Warehouse  ",
        "address": "Bengaluru",
        "is_default": True,
        "is_active": True,
    }


def test_product_validation() -> None:
    """Product schema validates and normalizes supported values."""
    request = ProductCreate(**build_product_payload())

    assert request.sku == "LAPTOP-001"
    assert request.name == "Business Laptop"
    assert request.purchase_price == Decimal("50000.00")
    assert request.selling_price == Decimal("65000.00")
    assert request.reorder_level == Decimal("5.0000")


def test_product_required_fields_are_validated() -> None:
    """Product SKU and name are required."""
    payload = build_product_payload()
    payload["sku"] = " "

    with pytest.raises(ValidationError):
        ProductCreate(**payload)

    payload = build_product_payload()
    payload["name"] = " "

    with pytest.raises(ValidationError):
        ProductCreate(**payload)


def test_negative_prices_are_rejected() -> None:
    """Product prices cannot be negative."""
    payload = build_product_payload()
    payload["purchase_price"] = "-1.00"

    with pytest.raises(ValidationError):
        ProductCreate(**payload)

    payload = build_product_payload()
    payload["selling_price"] = "-1.00"

    with pytest.raises(ValidationError):
        ProductCreate(**payload)


def test_negative_reorder_level_is_rejected() -> None:
    """Product reorder level cannot be negative."""
    payload = build_product_payload()
    payload["reorder_level"] = "-1.0000"

    with pytest.raises(ValidationError):
        ProductCreate(**payload)


def test_warehouse_validation() -> None:
    """Warehouse schema validates and normalizes supported values."""
    request = WarehouseCreate(**build_warehouse_payload())

    assert request.code == "MAIN"
    assert request.name == "Main Warehouse"
    assert request.address == "Bengaluru"
    assert request.is_default is True


def test_warehouse_required_fields_are_validated() -> None:
    """Warehouse code and name are required."""
    payload = build_warehouse_payload()
    payload["code"] = " "

    with pytest.raises(ValidationError):
        WarehouseCreate(**payload)

    payload = build_warehouse_payload()
    payload["name"] = " "

    with pytest.raises(ValidationError):
        WarehouseCreate(**payload)


def test_negative_stock_quantities_are_rejected() -> None:
    """Stock balance quantities cannot be negative."""
    balance = StockBalance(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        warehouse_id=uuid.uuid4(),
        quantity_on_hand=Decimal("-1.0000"),
        quantity_reserved=Decimal("0.0000"),
        quantity_available=Decimal("0.0000"),
        last_updated=datetime.now(),
    )

    with pytest.raises(ValidationError):
        StockBalanceResponse.model_validate(balance)


def test_stock_movement_quantity_is_positive() -> None:
    """Stock movement quantity must be greater than zero."""
    with pytest.raises(ValidationError):
        StockMovementCreate(
            product_id=uuid.uuid4(),
            warehouse_id=uuid.uuid4(),
            movement_type=MovementType.PURCHASE,
            quantity=Decimal("0.0000"),
        )


def test_movement_enum_validation() -> None:
    """Stock movement type must be a valid enum."""
    with pytest.raises(ValidationError):
        StockMovementCreate(
            product_id=uuid.uuid4(),
            warehouse_id=uuid.uuid4(),
            movement_type="invalid",
            quantity=Decimal("1.0000"),
        )


def test_product_response_orm_serialization() -> None:
    """Product responses serialize from SQLAlchemy model attributes."""
    product_id = uuid.uuid4()
    business_id = uuid.uuid4()
    product = Product(
        id=product_id,
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
        is_active=True,
    )

    response = ProductResponse.model_validate(product)

    assert response.id == product_id
    assert response.business_id == business_id
    assert response.sku == "LAPTOP-001"
    assert response.purchase_price == Decimal("50000.00")


def test_warehouse_response_orm_serialization() -> None:
    """Warehouse responses serialize from SQLAlchemy model attributes."""
    warehouse_id = uuid.uuid4()
    warehouse = Warehouse(
        id=warehouse_id,
        business_id=uuid.uuid4(),
        code="MAIN",
        name="Main Warehouse",
        address="Bengaluru",
        is_default=True,
        is_active=True,
    )

    response = WarehouseResponse.model_validate(warehouse)

    assert response.id == warehouse_id
    assert response.code == "MAIN"
    assert response.is_default is True


def test_stock_movement_response_orm_serialization() -> None:
    """Stock movement responses serialize from SQLAlchemy model attributes."""
    movement_id = uuid.uuid4()
    reference_id = uuid.uuid4()
    movement = StockMovement(
        id=movement_id,
        business_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        warehouse_id=uuid.uuid4(),
        movement_type=MovementType.PURCHASE,
        quantity=Decimal("10.0000"),
        reference_type="purchase_invoice",
        reference_id=reference_id,
        notes="Initial purchase receipt",
    )

    response = StockMovementResponse.model_validate(movement)

    assert response.id == movement_id
    assert response.movement_type == MovementType.PURCHASE
    assert response.reference_id == reference_id


def test_inventory_responses_hide_internal_fields() -> None:
    """Inventory responses do not expose audit, soft-delete, or version fields."""
    product = Product(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        sku="LAPTOP-001",
        name="Business Laptop",
        unit_of_measure="pcs",
        purchase_price=Decimal("50000.00"),
        selling_price=Decimal("65000.00"),
        reorder_level=Decimal("5.0000"),
        is_active=True,
    )

    payload = ProductResponse.model_validate(product).model_dump()

    assert "created_at" not in payload
    assert "updated_at" not in payload
    assert "created_by" not in payload
    assert "updated_by" not in payload
    assert "is_deleted" not in payload
    assert "deleted_at" not in payload
    assert "version" not in payload
