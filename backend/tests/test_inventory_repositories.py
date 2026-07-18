"""Tests for Inventory Management repositories."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.business.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
from app.common.filters import FilterCondition, FilterParams
from app.common.pagination import PaginationParams
from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.modules.inventory.models import (
    MovementType,
    Product,
    StockBalance,
    StockMovement,
    Warehouse,
)
from app.modules.inventory.repository import (
    ProductRepository,
    StockBalanceRepository,
    StockMovementRepository,
    WarehouseRepository,
)
from app.modules.inventory.schemas import (
    ProductCreate,
    ProductUpdate,
    StockMovementCreate,
    WarehouseCreate,
    WarehouseUpdate,
)

pytestmark = pytest.mark.asyncio

EXPECTED_PRODUCT_CRUD_FLUSHES = 3
EXPECTED_WAREHOUSE_CRUD_FLUSHES = 3
EXPECTED_BALANCE_CRUD_FLUSHES = 2
EXPECTED_MOVEMENT_CRUD_FLUSHES = 1


class ScalarCollection:
    """Simple scalar collection test double."""

    def __init__(self, items: list[Any]) -> None:
        """Initialize with scalar items."""
        self._items = items

    def all(self) -> list[Any]:
        """Return scalar items."""
        return self._items

    def unique(self) -> "ScalarCollection":
        """Return unique scalar collection."""
        return self


class ExecuteResult:
    """Simple async session execute result test double."""

    def __init__(
        self,
        *,
        one_or_none: Any = None,
        one: Any = 0,
        items: list[Any] | None = None,
    ) -> None:
        """Initialize result values."""
        self._one_or_none = one_or_none
        self._one = one
        self._items = items or []

    def scalar_one_or_none(self) -> Any:
        """Return one scalar value or none."""
        return self._one_or_none

    def scalar_one(self) -> Any:
        """Return one scalar value."""
        return self._one

    def scalars(self) -> ScalarCollection:
        """Return scalar collection."""
        return ScalarCollection(self._items)


def build_session_mock() -> AsyncSession:
    """Build an async session mock for repository tests."""
    session = Mock(spec=AsyncSession)
    session.add = Mock()
    session.add_all = Mock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return cast(AsyncSession, session)


def build_product_create_request() -> ProductCreate:
    """Build a valid product create request."""
    return ProductCreate(
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


def build_warehouse_create_request() -> WarehouseCreate:
    """Build a valid warehouse create request."""
    return WarehouseCreate(
        code="MAIN",
        name="Main Warehouse",
        address="Bengaluru",
        is_default=True,
    )


def build_stock_movement_create_request(
    product_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
) -> StockMovementCreate:
    """Build a valid stock movement create request."""
    return StockMovementCreate(
        product_id=product_id or uuid.uuid4(),
        warehouse_id=warehouse_id or uuid.uuid4(),
        movement_type=MovementType.PURCHASE,
        quantity=Decimal("10.0000"),
        reference_type="purchase_invoice",
        reference_id=uuid.uuid4(),
        notes="Initial purchase receipt",
    )


def build_product() -> Product:
    """Build a product model."""
    return Product(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        sku="LAPTOP-001",
        name="Business Laptop",
        category="Hardware",
        unit_of_measure="pcs",
        barcode="8900000000012",
        purchase_price=Decimal("50000.00"),
        selling_price=Decimal("65000.00"),
        reorder_level=Decimal("5.0000"),
        is_active=True,
    )


def build_warehouse() -> Warehouse:
    """Build a warehouse model."""
    return Warehouse(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        code="MAIN",
        name="Main Warehouse",
        address="Bengaluru",
        is_default=True,
        is_active=True,
    )


def build_stock_balance() -> StockBalance:
    """Build a stock balance model."""
    return StockBalance(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        warehouse_id=uuid.uuid4(),
        quantity_on_hand=Decimal("25.0000"),
        quantity_reserved=Decimal("5.0000"),
        quantity_available=Decimal("20.0000"),
    )


def build_stock_movement() -> StockMovement:
    """Build a stock movement model."""
    return StockMovement(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        warehouse_id=uuid.uuid4(),
        movement_type=MovementType.PURCHASE,
        quantity=Decimal("10.0000"),
        reference_type="purchase_invoice",
        reference_id=uuid.uuid4(),
        notes="Initial purchase receipt",
    )


async def test_product_repository_crud_and_flush_behavior() -> None:
    """Product repository creates, updates, and soft-deletes products."""
    session = build_session_mock()
    repository = ProductRepository(session)
    business_id = uuid.uuid4()
    product = await repository.create(
        build_product_create_request(),
        business_id=business_id,
    )

    assert isinstance(product, Product)
    assert product.business_id == business_id
    assert product.sku == "LAPTOP-001"
    cast(Any, session.add).assert_called_with(product)

    await repository.update(product, ProductUpdate(name="Updated Laptop"))
    assert product.name == "Updated Laptop"

    await repository.delete(product)
    assert product.is_deleted is True
    assert cast(Any, session.flush).await_count == EXPECTED_PRODUCT_CRUD_FLUSHES
    cast(Any, session.commit).assert_not_awaited()


async def test_product_lookup_filtering_sorting_search_and_exists() -> None:
    """Product repository supports lookup, filtering, sorting, and search."""
    session = build_session_mock()
    product = build_product()
    cast(Any, session.execute).return_value = ExecuteResult(
        one_or_none=product,
        one=1,
        items=[product],
    )
    repository = ProductRepository(session)

    assert await repository.get_by_id(product.id) is product
    assert (
        await repository.get_by_sku(
            business_id=product.business_id,
            sku=product.sku,
        )
        is product
    )
    assert (
        await repository.get_by_barcode(
            business_id=product.business_id,
            barcode=cast(str, product.barcode),
        )
        is product
    )

    page = await repository.list(
        business_id=product.business_id,
        pagination=PaginationParams(page=1, size=10),
        filters=FilterParams(
            filters=[
                FilterCondition(field="is_active", operator="eq", value=True)
            ],
        ),
        sort="name",
        category="Hardware",
        is_active=True,
    )
    search_page = await repository.search(
        business_id=product.business_id,
        query="Laptop",
        pagination=PaginationParams(page=1, size=10),
    )

    assert page.items == [product]
    assert search_page.items == [product]
    assert page.meta.total == 1
    assert (
        await repository.exists(
            business_id=product.business_id,
            sku=product.sku,
        )
        is True
    )


async def test_warehouse_repository_crud_and_flush_behavior() -> None:
    """Warehouse repository creates, updates, and soft-deletes warehouses."""
    session = build_session_mock()
    repository = WarehouseRepository(session)
    business_id = uuid.uuid4()
    warehouse = await repository.create(
        build_warehouse_create_request(),
        business_id=business_id,
    )

    assert isinstance(warehouse, Warehouse)
    assert warehouse.business_id == business_id
    assert warehouse.code == "MAIN"

    await repository.update(warehouse, WarehouseUpdate(name="Updated Warehouse"))
    assert warehouse.name == "Updated Warehouse"

    await repository.delete(warehouse)
    assert warehouse.is_deleted is True
    assert cast(Any, session.flush).await_count == EXPECTED_WAREHOUSE_CRUD_FLUSHES
    cast(Any, session.commit).assert_not_awaited()


async def test_warehouse_lookup_filtering_sorting_search_and_exists() -> None:
    """Warehouse repository supports lookup, filtering, sorting, and search."""
    session = build_session_mock()
    warehouse = build_warehouse()
    cast(Any, session.execute).return_value = ExecuteResult(
        one_or_none=warehouse,
        one=1,
        items=[warehouse],
    )
    repository = WarehouseRepository(session)

    assert await repository.get_by_id(warehouse.id) is warehouse
    assert (
        await repository.get_by_code(
            business_id=warehouse.business_id,
            code=warehouse.code,
        )
        is warehouse
    )

    page = await repository.list(
        business_id=warehouse.business_id,
        pagination=PaginationParams(page=1, size=10),
        filters=FilterParams(
            filters=[
                FilterCondition(field="is_active", operator="eq", value=True)
            ],
        ),
        sort="code",
        is_active=True,
    )
    search_page = await repository.search(
        business_id=warehouse.business_id,
        query="Main",
        pagination=PaginationParams(page=1, size=10),
    )

    assert page.items == [warehouse]
    assert search_page.items == [warehouse]
    assert page.meta.total == 1
    assert (
        await repository.exists(
            business_id=warehouse.business_id,
            code=warehouse.code,
        )
        is True
    )


async def test_stock_balance_repository_crud_filtering_and_pagination() -> None:
    """Stock balance repository creates, updates, lists, and looks up balances."""
    session = build_session_mock()
    balance = build_stock_balance()
    cast(Any, session.execute).return_value = ExecuteResult(
        one_or_none=balance,
        one=1,
        items=[balance],
    )
    repository = StockBalanceRepository(session)

    created = await repository.create(
        business_id=balance.business_id,
        product_id=balance.product_id,
        warehouse_id=balance.warehouse_id,
        quantity_on_hand=Decimal("25.0000"),
        quantity_reserved=Decimal("5.0000"),
        quantity_available=Decimal("20.0000"),
    )
    assert isinstance(created, StockBalance)
    assert created.quantity_available == Decimal("20.0000")

    await repository.update(created, quantity_available=Decimal("22.0000"))
    assert created.quantity_available == Decimal("22.0000")

    assert await repository.get_by_id(balance.id) is balance
    assert (
        await repository.get_by_product_and_warehouse(
            business_id=balance.business_id,
            product_id=balance.product_id,
            warehouse_id=balance.warehouse_id,
        )
        is balance
    )
    assert await repository.get_by_product(
        business_id=balance.business_id,
        product_id=balance.product_id,
    ) == [balance]

    page = await repository.list(
        business_id=balance.business_id,
        pagination=PaginationParams(page=1, size=10),
        filters=FilterParams(
            filters=[
                FilterCondition(
                    field="warehouse_id",
                    operator="eq",
                    value=str(balance.warehouse_id),
                )
            ],
        ),
        product_id=balance.product_id,
        warehouse_id=balance.warehouse_id,
    )

    assert page.items == [balance]
    assert page.meta.total == 1
    assert cast(Any, session.flush).await_count == EXPECTED_BALANCE_CRUD_FLUSHES
    cast(Any, session.commit).assert_not_awaited()


async def test_stock_movement_repository_crud_filtering_and_pagination() -> None:
    """Stock movement repository creates and queries movements."""
    session = build_session_mock()
    movement = build_stock_movement()
    cast(Any, session.execute).return_value = ExecuteResult(
        one_or_none=movement,
        one=1,
        items=[movement],
    )
    repository = StockMovementRepository(session)
    request = build_stock_movement_create_request(
        movement.product_id,
        movement.warehouse_id,
    )

    created = await repository.create(request, business_id=movement.business_id)
    assert isinstance(created, StockMovement)
    assert created.business_id == movement.business_id
    assert created.movement_type == MovementType.PURCHASE

    assert await repository.get_by_id(movement.id) is movement

    now = datetime.now(tz=UTC)
    page = await repository.list(
        business_id=movement.business_id,
        pagination=PaginationParams(page=1, size=10),
        filters=FilterParams(
            filters=[
                FilterCondition(
                    field="movement_type",
                    operator="eq",
                    value=MovementType.PURCHASE.value,
                )
            ],
        ),
        sort="-created_at",
        product_id=movement.product_id,
        warehouse_id=movement.warehouse_id,
        movement_type=MovementType.PURCHASE,
        created_at_from=now,
        created_at_to=now,
    )
    product_page = await repository.list_by_product(
        business_id=movement.business_id,
        product_id=movement.product_id,
        pagination=PaginationParams(page=1, size=10),
    )
    warehouse_page = await repository.list_by_warehouse(
        business_id=movement.business_id,
        warehouse_id=movement.warehouse_id,
        pagination=PaginationParams(page=1, size=10),
    )
    reference_page = await repository.list_by_reference(
        business_id=movement.business_id,
        reference_type=cast(str, movement.reference_type),
        reference_id=cast(uuid.UUID, movement.reference_id),
        pagination=PaginationParams(page=1, size=10),
    )

    assert page.items == [movement]
    assert product_page.items == [movement]
    assert warehouse_page.items == [movement]
    assert reference_page.items == [movement]
    assert cast(Any, session.flush).await_count == EXPECTED_MOVEMENT_CRUD_FLUSHES
    cast(Any, session.commit).assert_not_awaited()


async def test_inventory_repositories_are_registered_in_unit_of_work() -> None:
    """SQLAlchemy Unit of Work exposes inventory repositories."""
    session = build_session_mock()
    unit_of_work = SQLAlchemyUnitOfWork(lambda: session)

    async with unit_of_work as active_uow:
        assert isinstance(active_uow.products, ProductRepository)
        assert isinstance(active_uow.warehouses, WarehouseRepository)
        assert isinstance(active_uow.stock_balances, StockBalanceRepository)
        assert isinstance(active_uow.stock_movements, StockMovementRepository)
        await active_uow.commit()

    cast(Any, session.commit).assert_awaited_once()
    cast(Any, session.rollback).assert_not_awaited()
    cast(Any, session.close).assert_awaited_once()
