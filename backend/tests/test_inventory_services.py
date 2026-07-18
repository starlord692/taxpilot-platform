"""Tests for Inventory Management services."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Self, cast

import pytest

import app.modules.business.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
from app.common.events import Event, EventDispatcher
from app.common.pagination import Page, PaginationParams
from app.modules.inventory.events import (
    ProductActivatedEvent,
    ProductCreatedEvent,
    ProductDeactivatedEvent,
    WarehouseCreatedEvent,
    WarehouseDeactivatedEvent,
)
from app.modules.inventory.exceptions import (
    ActiveStockExistsException,
    DefaultWarehouseException,
    DuplicateProductException,
    DuplicateWarehouseException,
    ProductNotFoundException,
)
from app.modules.inventory.models import Product, StockBalance, Warehouse
from app.modules.inventory.schemas import (
    ProductCreate,
    ProductUpdate,
    WarehouseCreate,
    WarehouseUpdate,
)
from app.modules.inventory.services import (
    InventoryService,
    ProductService,
    WarehouseService,
)
from app.modules.inventory.services.inventory_service import InventoryUnitOfWork
from app.modules.inventory.services.product_service import ProductUnitOfWork
from app.modules.inventory.services.warehouse_service import WarehouseUnitOfWork

pytestmark = pytest.mark.asyncio


class CapturingEventDispatcher(EventDispatcher):
    """Event dispatcher that records dispatched events."""

    def __init__(self) -> None:
        """Initialize captured events."""
        super().__init__()
        self.events: list[Event] = []

    async def dispatch(self, event: Event) -> None:
        """Record and dispatch an event."""
        self.events.append(event)
        await super().dispatch(event)


class FakeProductRepository:
    """Fake product repository for service tests."""

    def __init__(
        self,
        products: list[Product] | None = None,
        *,
        fail_create: bool = False,
    ) -> None:
        """Initialize fake repository."""
        self.products = products or []
        self.fail_create = fail_create

    async def create(
        self,
        request: ProductCreate,
        *,
        business_id: uuid.UUID,
    ) -> Product:
        """Create a fake product."""
        if self.fail_create:
            raise RuntimeError("product create failed")
        product = Product(
            id=uuid.uuid4(),
            business_id=business_id,
            **request.model_dump(),
        )
        self.products.append(product)
        return product

    async def get_by_id(self, product_id: uuid.UUID) -> Product | None:
        """Return product by id."""
        return next(
            (product for product in self.products if product.id == product_id),
            None,
        )

    async def get_by_sku(
        self,
        *,
        business_id: uuid.UUID,
        sku: str,
    ) -> Product | None:
        """Return product by business SKU."""
        return next(
            (
                product
                for product in self.products
                if product.business_id == business_id and product.sku == sku
            ),
            None,
        )

    async def get_by_barcode(
        self,
        *,
        business_id: uuid.UUID,
        barcode: str,
    ) -> Product | None:
        """Return product by business barcode."""
        return next(
            (
                product
                for product in self.products
                if product.business_id == business_id and product.barcode == barcode
            ),
            None,
        )

    async def list(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        sort: str | None = None,
        category: str | None = None,
        is_active: bool | None = None,
    ) -> Page[Product]:
        """Return fake products for a business."""
        _ = sort
        params = pagination or PaginationParams()
        items = [
            product
            for product in self.products
            if product.business_id == business_id
            and (category is None or product.category == category)
            and (is_active is None or product.is_active == is_active)
        ]
        return Page.create(items=items, total=len(items), params=params)

    async def search(
        self,
        *,
        business_id: uuid.UUID,
        query: str,
        pagination: PaginationParams | None = None,
    ) -> Page[Product]:
        """Search fake products."""
        params = pagination or PaginationParams()
        normalized = query.casefold()
        items = [
            product
            for product in self.products
            if product.business_id == business_id
            and (
                normalized in product.sku.casefold()
                or normalized in product.name.casefold()
                or (
                    product.barcode is not None
                    and normalized in product.barcode.casefold()
                )
                or (
                    product.category is not None
                    and normalized in product.category.casefold()
                )
            )
        ]
        return Page.create(items=items, total=len(items), params=params)

    async def update(self, product: Product, request: ProductUpdate) -> Product:
        """Update fake product."""
        for field_name, value in request.model_dump(exclude_unset=True).items():
            setattr(product, field_name, value)
        return product


class FakeWarehouseRepository:
    """Fake warehouse repository for service tests."""

    def __init__(self, warehouses: list[Warehouse] | None = None) -> None:
        """Initialize fake repository."""
        self.warehouses = warehouses or []

    async def create(
        self,
        request: WarehouseCreate,
        *,
        business_id: uuid.UUID,
    ) -> Warehouse:
        """Create a fake warehouse."""
        warehouse = Warehouse(
            id=uuid.uuid4(),
            business_id=business_id,
            **request.model_dump(),
        )
        self.warehouses.append(warehouse)
        return warehouse

    async def get_by_id(self, warehouse_id: uuid.UUID) -> Warehouse | None:
        """Return warehouse by id."""
        return next(
            (
                warehouse
                for warehouse in self.warehouses
                if warehouse.id == warehouse_id
            ),
            None,
        )

    async def get_by_code(
        self,
        *,
        business_id: uuid.UUID,
        code: str,
    ) -> Warehouse | None:
        """Return warehouse by business code."""
        return next(
            (
                warehouse
                for warehouse in self.warehouses
                if warehouse.business_id == business_id and warehouse.code == code
            ),
            None,
        )

    async def list(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        sort: str | None = None,
        is_active: bool | None = None,
    ) -> Page[Warehouse]:
        """Return fake warehouses for a business."""
        _ = sort
        params = pagination or PaginationParams()
        items = [
            warehouse
            for warehouse in self.warehouses
            if warehouse.business_id == business_id
            and (is_active is None or warehouse.is_active == is_active)
        ]
        return Page.create(items=items, total=len(items), params=params)

    async def update(
        self,
        warehouse: Warehouse,
        request: WarehouseUpdate,
    ) -> Warehouse:
        """Update fake warehouse."""
        for field_name, value in request.model_dump(exclude_unset=True).items():
            setattr(warehouse, field_name, value)
        return warehouse


class FakeStockBalanceRepository:
    """Fake stock balance repository for service tests."""

    def __init__(self, balances: list[StockBalance] | None = None) -> None:
        """Initialize fake repository."""
        self.balances = balances or []

    async def get_by_id(self, balance_id: uuid.UUID) -> StockBalance | None:
        """Return stock balance by id."""
        return next(
            (balance for balance in self.balances if balance.id == balance_id),
            None,
        )

    async def get_by_product(
        self,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> list[StockBalance]:
        """Return stock balances for a product."""
        return [
            balance
            for balance in self.balances
            if balance.business_id == business_id and balance.product_id == product_id
        ]

    async def get_by_product_and_warehouse(
        self,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
    ) -> StockBalance | None:
        """Return one stock balance."""
        return next(
            (
                balance
                for balance in self.balances
                if balance.business_id == business_id
                and balance.product_id == product_id
                and balance.warehouse_id == warehouse_id
            ),
            None,
        )

    async def list(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        product_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
    ) -> Page[StockBalance]:
        """Return stock balances for a business."""
        params = pagination or PaginationParams()
        items = [
            balance
            for balance in self.balances
            if balance.business_id == business_id
            and (product_id is None or balance.product_id == product_id)
            and (warehouse_id is None or balance.warehouse_id == warehouse_id)
        ]
        return Page.create(items=items, total=len(items), params=params)


class FakeInventoryUnitOfWork:
    """Fake Unit of Work for inventory service tests."""

    def __init__(
        self,
        *,
        product_repository: FakeProductRepository | None = None,
        warehouse_repository: FakeWarehouseRepository | None = None,
        stock_balance_repository: FakeStockBalanceRepository | None = None,
    ) -> None:
        """Initialize fake repositories."""
        self.products = product_repository or FakeProductRepository()
        self.warehouses = warehouse_repository or FakeWarehouseRepository()
        self.stock_balances = (
            stock_balance_repository or FakeStockBalanceRepository()
        )
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> Self:
        """Enter fake transaction scope."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Rollback uncommitted fake transactions."""
        if exc_type is not None or not self.committed:
            self.rolled_back = True

    async def commit(self) -> None:
        """Mark transaction committed."""
        self.committed = True


def build_product(*, business_id: uuid.UUID | None = None) -> Product:
    """Build a product model."""
    return Product(
        id=uuid.uuid4(),
        business_id=business_id or uuid.uuid4(),
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


def build_product_request() -> ProductCreate:
    """Build a product create request."""
    return ProductCreate(
        sku="LAPTOP-001",
        name="Business Laptop",
        category="Hardware",
        unit_of_measure="pcs",
        barcode="8900000000012",
        purchase_price=Decimal("50000.00"),
        selling_price=Decimal("65000.00"),
        reorder_level=Decimal("5.0000"),
    )


def build_warehouse(
    *,
    business_id: uuid.UUID | None = None,
    is_default: bool = False,
) -> Warehouse:
    """Build a warehouse model."""
    return Warehouse(
        id=uuid.uuid4(),
        business_id=business_id or uuid.uuid4(),
        code="MAIN",
        name="Main Warehouse",
        address="Bengaluru",
        is_default=is_default,
        is_active=True,
    )


def build_warehouse_request(*, is_default: bool = False) -> WarehouseCreate:
    """Build a warehouse create request."""
    return WarehouseCreate(
        code="MAIN",
        name="Main Warehouse",
        address="Bengaluru",
        is_default=is_default,
    )


def build_balance(
    *,
    business_id: uuid.UUID,
    product_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
    quantity_on_hand: Decimal = Decimal("10.0000"),
) -> StockBalance:
    """Build a stock balance model."""
    return StockBalance(
        id=uuid.uuid4(),
        business_id=business_id,
        product_id=product_id or uuid.uuid4(),
        warehouse_id=warehouse_id or uuid.uuid4(),
        quantity_on_hand=quantity_on_hand,
        quantity_reserved=Decimal("0.0000"),
        quantity_available=quantity_on_hand,
        last_updated=datetime.now(tz=UTC),
    )


def build_product_service(
    uow: FakeInventoryUnitOfWork,
    dispatcher: CapturingEventDispatcher,
) -> ProductService:
    """Build product service with fake dependencies."""
    return ProductService(
        unit_of_work_factory=lambda: cast(ProductUnitOfWork, uow),
        event_dispatcher=dispatcher,
    )


def build_warehouse_service(
    uow: FakeInventoryUnitOfWork,
    dispatcher: CapturingEventDispatcher,
) -> WarehouseService:
    """Build warehouse service with fake dependencies."""
    return WarehouseService(
        unit_of_work_factory=lambda: cast(WarehouseUnitOfWork, uow),
        event_dispatcher=dispatcher,
    )


def build_inventory_service(uow: FakeInventoryUnitOfWork) -> InventoryService:
    """Build inventory service with fake dependencies."""
    return InventoryService(
        unit_of_work_factory=lambda: cast(InventoryUnitOfWork, uow)
    )


async def test_product_lifecycle_and_events() -> None:
    """Product service creates, updates, deactivates, and activates products."""
    dispatcher = CapturingEventDispatcher()
    uow = FakeInventoryUnitOfWork()
    service = build_product_service(uow, dispatcher)
    business_id = uuid.uuid4()

    created = await service.create_product(
        build_product_request(),
        business_id=business_id,
    )
    updated = await service.update_product(
        created.id,
        ProductUpdate(name="Updated Laptop"),
        business_id=business_id,
    )
    deactivated = await service.deactivate_product(created.id, business_id=business_id)
    activated = await service.activate_product(created.id, business_id=business_id)

    assert created.sku == "LAPTOP-001"
    assert updated.name == "Updated Laptop"
    assert deactivated.is_active is False
    assert activated.is_active is True
    assert isinstance(dispatcher.events[0], ProductCreatedEvent)
    assert isinstance(dispatcher.events[2], ProductDeactivatedEvent)
    assert isinstance(dispatcher.events[3], ProductActivatedEvent)


async def test_duplicate_sku_and_barcode_are_rejected() -> None:
    """Product service rejects duplicate SKU and barcode values."""
    existing = build_product()
    service = build_product_service(
        FakeInventoryUnitOfWork(
            product_repository=FakeProductRepository([existing])
        ),
        CapturingEventDispatcher(),
    )

    with pytest.raises(DuplicateProductException):
        await service.create_product(
            build_product_request(),
            business_id=existing.business_id,
        )

    request = build_product_request().model_copy(
        update={"sku": "LAPTOP-002"}
    )
    with pytest.raises(DuplicateProductException):
        await service.create_product(request, business_id=existing.business_id)


async def test_product_deactivation_requires_no_active_stock() -> None:
    """Product cannot be deactivated while stock exists."""
    product = build_product()
    balance = build_balance(
        business_id=product.business_id,
        product_id=product.id,
        quantity_on_hand=Decimal("1.0000"),
    )
    service = build_product_service(
        FakeInventoryUnitOfWork(
            product_repository=FakeProductRepository([product]),
            stock_balance_repository=FakeStockBalanceRepository([balance]),
        ),
        CapturingEventDispatcher(),
    )

    with pytest.raises(ActiveStockExistsException):
        await service.deactivate_product(product.id, business_id=product.business_id)


async def test_product_business_isolation() -> None:
    """Product service rejects cross-business access."""
    product = build_product()
    service = build_product_service(
        FakeInventoryUnitOfWork(
            product_repository=FakeProductRepository([product])
        ),
        CapturingEventDispatcher(),
    )

    with pytest.raises(ProductNotFoundException):
        await service.get_product(product.id, business_id=uuid.uuid4())


async def test_warehouse_lifecycle_and_events() -> None:
    """Warehouse service creates, updates, and deactivates warehouses."""
    dispatcher = CapturingEventDispatcher()
    uow = FakeInventoryUnitOfWork()
    service = build_warehouse_service(uow, dispatcher)
    business_id = uuid.uuid4()

    created = await service.create_warehouse(
        build_warehouse_request(),
        business_id=business_id,
    )
    updated = await service.update_warehouse(
        created.id,
        WarehouseUpdate(name="Updated Warehouse"),
        business_id=business_id,
    )
    deactivated = await service.deactivate_warehouse(
        created.id,
        business_id=business_id,
    )

    assert created.code == "MAIN"
    assert updated.name == "Updated Warehouse"
    assert deactivated.is_active is False
    assert isinstance(dispatcher.events[0], WarehouseCreatedEvent)
    assert isinstance(dispatcher.events[2], WarehouseDeactivatedEvent)


async def test_duplicate_warehouse_code_is_rejected() -> None:
    """Warehouse service rejects duplicate business warehouse codes."""
    existing = build_warehouse()
    service = build_warehouse_service(
        FakeInventoryUnitOfWork(
            warehouse_repository=FakeWarehouseRepository([existing])
        ),
        CapturingEventDispatcher(),
    )

    with pytest.raises(DuplicateWarehouseException):
        await service.create_warehouse(
            build_warehouse_request(),
            business_id=existing.business_id,
        )


async def test_default_warehouse_rules() -> None:
    """Only one default warehouse is allowed and it cannot be deactivated."""
    existing_default = build_warehouse(is_default=True)
    service = build_warehouse_service(
        FakeInventoryUnitOfWork(
            warehouse_repository=FakeWarehouseRepository([existing_default])
        ),
        CapturingEventDispatcher(),
    )

    with pytest.raises(DefaultWarehouseException):
        await service.create_warehouse(
            build_warehouse_request(is_default=True).model_copy(
                update={"code": "SECOND"}
            ),
            business_id=existing_default.business_id,
        )

    with pytest.raises(DefaultWarehouseException):
        await service.deactivate_warehouse(
            existing_default.id,
            business_id=existing_default.business_id,
        )


async def test_warehouse_deactivation_requires_no_active_stock() -> None:
    """Warehouse cannot be deactivated while stock exists."""
    warehouse = build_warehouse()
    balance = build_balance(
        business_id=warehouse.business_id,
        warehouse_id=warehouse.id,
        quantity_on_hand=Decimal("1.0000"),
    )
    service = build_warehouse_service(
        FakeInventoryUnitOfWork(
            warehouse_repository=FakeWarehouseRepository([warehouse]),
            stock_balance_repository=FakeStockBalanceRepository([balance]),
        ),
        CapturingEventDispatcher(),
    )

    with pytest.raises(ActiveStockExistsException):
        await service.deactivate_warehouse(
            warehouse.id,
            business_id=warehouse.business_id,
        )


async def test_inventory_read_operations() -> None:
    """Inventory service reads balances and searches products by business."""
    product = build_product()
    warehouse = build_warehouse(business_id=product.business_id)
    balance = build_balance(
        business_id=product.business_id,
        product_id=product.id,
        warehouse_id=warehouse.id,
    )
    uow = FakeInventoryUnitOfWork(
        product_repository=FakeProductRepository([product]),
        stock_balance_repository=FakeStockBalanceRepository([balance]),
    )
    service = build_inventory_service(uow)

    stock_balance = await service.get_stock_balance(
        balance.id,
        business_id=balance.business_id,
    )
    product_stock = await service.get_product_stock(
        product.id,
        business_id=product.business_id,
    )
    warehouse_stock = await service.get_warehouse_stock(
        warehouse.id,
        business_id=product.business_id,
    )
    search_page = await service.search_inventory(product.business_id, "Laptop")

    assert stock_balance.id == balance.id
    assert product_stock[0].id == balance.id
    assert warehouse_stock.items[0].id == balance.id
    assert search_page.items[0].id == product.id


async def test_transaction_rolls_back_on_failure() -> None:
    """Unit of Work rolls back when product persistence fails."""
    uow = FakeInventoryUnitOfWork(
        product_repository=FakeProductRepository(fail_create=True)
    )
    service = build_product_service(uow, CapturingEventDispatcher())

    with pytest.raises(RuntimeError):
        await service.create_product(build_product_request(), business_id=uuid.uuid4())

    assert uow.committed is False
    assert uow.rolled_back is True
