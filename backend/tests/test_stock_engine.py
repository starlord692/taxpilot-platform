"""Tests for the Inventory Stock Movement Engine."""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import cast

import pytest

from app.common.events import Event, EventDispatcher
from app.modules.inventory.events import (
    StockAdjustedEvent,
    StockIssuedEvent,
    StockReceivedEvent,
    StockReleasedEvent,
    StockReservedEvent,
    StockTransferredEvent,
)
from app.modules.inventory.exceptions import (
    InventoryValidationException,
    NegativeStockException,
)
from app.modules.inventory.models import MovementType, Product, StockBalance
from app.modules.inventory.models.stock_movement import StockMovement
from app.modules.inventory.models.warehouse import Warehouse
from app.modules.inventory.schemas import StockMovementCreate
from app.modules.inventory.services.stock_engine import (
    StockEngine,
    StockEngineUnitOfWork,
)

TRANSFER_MOVEMENT_COUNT = 2


@dataclass
class SourceLine:
    """Minimal stock source line for engine tests."""

    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    quantity: Decimal
    description: str = "Tracked item"


@dataclass
class SourceDocument:
    """Minimal purchase or sales source document for engine tests."""

    id: uuid.UUID
    business_id: uuid.UUID
    lines: list[SourceLine] = field(default_factory=list)


class CapturingEventDispatcher(EventDispatcher):
    """Capture published events for assertions."""

    def __init__(self) -> None:
        """Initialize captured event storage."""
        super().__init__()
        self.events: list[Event] = []

    async def dispatch(self, event: Event) -> None:
        """Capture an event."""
        self.events.append(event)
        await super().dispatch(event)


class FakeProductRepository:
    """In-memory product repository for stock engine tests."""

    def __init__(self, products: dict[uuid.UUID, Product]) -> None:
        """Initialize products."""
        self._products = products

    async def get_by_id(self, product_id: uuid.UUID) -> Product | None:
        """Return product by UUID."""
        return self._products.get(product_id)


class FakeWarehouseRepository:
    """In-memory warehouse repository for stock engine tests."""

    def __init__(self, warehouses: dict[uuid.UUID, Warehouse]) -> None:
        """Initialize warehouses."""
        self._warehouses = warehouses

    async def get_by_id(self, warehouse_id: uuid.UUID) -> Warehouse | None:
        """Return warehouse by UUID."""
        return self._warehouses.get(warehouse_id)


class FakeStockBalanceRepository:
    """In-memory stock balance repository for stock engine tests."""

    def __init__(self) -> None:
        """Initialize balances."""
        self.balances: dict[tuple[uuid.UUID, uuid.UUID, uuid.UUID], StockBalance] = {}
        self.fail_update = False

    async def create(
        self,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        quantity_on_hand: Decimal = Decimal("0.0000"),
        quantity_reserved: Decimal = Decimal("0.0000"),
        quantity_available: Decimal = Decimal("0.0000"),
    ) -> StockBalance:
        """Create a stock balance."""
        balance = StockBalance(
            id=uuid.uuid4(),
            business_id=business_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=quantity_reserved,
            quantity_available=quantity_available,
        )
        self.balances[(business_id, product_id, warehouse_id)] = balance
        return balance

    async def update(
        self,
        balance: StockBalance,
        *,
        quantity_on_hand: Decimal | None = None,
        quantity_reserved: Decimal | None = None,
        quantity_available: Decimal | None = None,
    ) -> StockBalance:
        """Update a stock balance."""
        if self.fail_update:
            raise RuntimeError("forced stock balance failure")
        if quantity_on_hand is not None:
            balance.quantity_on_hand = quantity_on_hand
        if quantity_reserved is not None:
            balance.quantity_reserved = quantity_reserved
        if quantity_available is not None:
            balance.quantity_available = quantity_available
        return balance

    async def get_by_product_and_warehouse(
        self,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
    ) -> StockBalance | None:
        """Return a stock balance."""
        return self.balances.get((business_id, product_id, warehouse_id))


class FakeStockMovementRepository:
    """In-memory stock movement repository for stock engine tests."""

    def __init__(self) -> None:
        """Initialize movements."""
        self.movements: list[StockMovement] = []

    async def create(
        self,
        request: StockMovementCreate,
        *,
        business_id: uuid.UUID,
    ) -> StockMovement:
        """Create a stock movement."""
        movement = StockMovement(
            id=uuid.uuid4(),
            business_id=business_id,
            **request.model_dump(),
        )
        self.movements.append(movement)
        return movement


class FakeStockUnitOfWork:
    """In-memory unit of work for stock engine tests."""

    def __init__(
        self,
        *,
        products: dict[uuid.UUID, Product],
        warehouses: dict[uuid.UUID, Warehouse],
    ) -> None:
        """Initialize fake repositories."""
        self.products = FakeProductRepository(products)
        self.warehouses = FakeWarehouseRepository(warehouses)
        self.stock_balances = FakeStockBalanceRepository()
        self.stock_movements = FakeStockMovementRepository()
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> "FakeStockUnitOfWork":
        """Enter the fake transaction."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Roll back when the fake transaction exits with an error."""
        if exc is not None:
            self.rolled_back = True

    async def commit(self) -> None:
        """Mark the fake transaction committed."""
        self.committed = True


@dataclass
class StockEngineFixture:
    """Reusable stock engine test fixture state."""

    business_id: uuid.UUID
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    second_warehouse_id: uuid.UUID
    uow: FakeStockUnitOfWork
    dispatcher: CapturingEventDispatcher
    engine: StockEngine


@pytest.fixture
def stock_engine_fixture() -> StockEngineFixture:
    """Create a stock engine with in-memory repositories."""
    business_id = uuid.uuid4()
    product_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    second_warehouse_id = uuid.uuid4()
    products = {
        product_id: Product(
            id=product_id,
            business_id=business_id,
            sku="SKU-001",
            name="Inventory Item",
            is_active=True,
        )
    }
    warehouses = {
        warehouse_id: Warehouse(
            id=warehouse_id,
            business_id=business_id,
            code="MAIN",
            name="Main Warehouse",
            is_active=True,
        ),
        second_warehouse_id: Warehouse(
            id=second_warehouse_id,
            business_id=business_id,
            code="AUX",
            name="Aux Warehouse",
            is_active=True,
        ),
    }
    uow = FakeStockUnitOfWork(products=products, warehouses=warehouses)
    dispatcher = CapturingEventDispatcher()
    engine = StockEngine(
        unit_of_work_factory=lambda: cast(StockEngineUnitOfWork, uow),
        event_dispatcher=dispatcher,
    )
    return StockEngineFixture(
        business_id=business_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        second_warehouse_id=second_warehouse_id,
        uow=uow,
        dispatcher=dispatcher,
        engine=engine,
    )


def source_document(
    fixture: StockEngineFixture,
    *,
    quantity: Decimal,
    warehouse_id: uuid.UUID | None = None,
) -> SourceDocument:
    """Create a source document with one stock line."""
    return SourceDocument(
        id=uuid.uuid4(),
        business_id=fixture.business_id,
        lines=[
            SourceLine(
                product_id=fixture.product_id,
                warehouse_id=warehouse_id or fixture.warehouse_id,
                quantity=quantity,
            )
        ],
    )


def balance_for(
    fixture: StockEngineFixture,
    warehouse_id: uuid.UUID | None = None,
) -> StockBalance:
    """Return the fixture stock balance."""
    key = (
        fixture.business_id,
        fixture.product_id,
        warehouse_id or fixture.warehouse_id,
    )
    return fixture.uow.stock_balances.balances[key]


@pytest.mark.asyncio
async def test_receive_purchase_creates_stock_movement_and_updates_balance(
    stock_engine_fixture: StockEngineFixture,
) -> None:
    """Purchase receipt increases stock and publishes an event."""
    document = source_document(stock_engine_fixture, quantity=Decimal("5.0000"))

    movements = await stock_engine_fixture.engine.receive_purchase(document)

    balance = balance_for(stock_engine_fixture)
    assert len(movements) == 1
    assert movements[0].movement_type == MovementType.PURCHASE
    assert balance.quantity_on_hand == Decimal("5.0000")
    assert balance.quantity_available == Decimal("5.0000")
    assert stock_engine_fixture.uow.committed is True
    assert isinstance(stock_engine_fixture.dispatcher.events[0], StockReceivedEvent)


@pytest.mark.asyncio
async def test_issue_sale_decreases_stock_and_publishes_event(
    stock_engine_fixture: StockEngineFixture,
) -> None:
    """Sale issue decreases stock and publishes an event."""
    await stock_engine_fixture.engine.receive_purchase(
        source_document(stock_engine_fixture, quantity=Decimal("10.0000"))
    )

    movements = await stock_engine_fixture.engine.issue_sale(
        source_document(stock_engine_fixture, quantity=Decimal("3.0000"))
    )

    balance = balance_for(stock_engine_fixture)
    assert movements[0].movement_type == MovementType.SALE
    assert balance.quantity_on_hand == Decimal("7.0000")
    assert balance.quantity_available == Decimal("7.0000")
    assert any(
        isinstance(event, StockIssuedEvent)
        for event in stock_engine_fixture.dispatcher.events
    )


@pytest.mark.asyncio
async def test_returns_update_stock_quantities(
    stock_engine_fixture: StockEngineFixture,
) -> None:
    """Sales and purchase returns update stock in opposite directions."""
    await stock_engine_fixture.engine.receive_purchase(
        source_document(stock_engine_fixture, quantity=Decimal("10.0000"))
    )
    await stock_engine_fixture.engine.return_sale(
        source_document(stock_engine_fixture, quantity=Decimal("2.0000"))
    )
    await stock_engine_fixture.engine.return_purchase(
        source_document(stock_engine_fixture, quantity=Decimal("4.0000"))
    )

    balance = balance_for(stock_engine_fixture)
    assert balance.quantity_on_hand == Decimal("8.0000")
    assert balance.quantity_available == Decimal("8.0000")


@pytest.mark.asyncio
async def test_adjust_stock_requires_reason_and_prevents_negative_stock(
    stock_engine_fixture: StockEngineFixture,
) -> None:
    """Stock adjustments require a reason and cannot create negative stock."""
    with pytest.raises(InventoryValidationException):
        await stock_engine_fixture.engine.adjust_stock(
            business_id=stock_engine_fixture.business_id,
            product_id=stock_engine_fixture.product_id,
            warehouse_id=stock_engine_fixture.warehouse_id,
            quantity_delta=Decimal("1.0000"),
            reason=" ",
        )

    with pytest.raises(NegativeStockException):
        await stock_engine_fixture.engine.adjust_stock(
            business_id=stock_engine_fixture.business_id,
            product_id=stock_engine_fixture.product_id,
            warehouse_id=stock_engine_fixture.warehouse_id,
            quantity_delta=Decimal("-1.0000"),
            reason="Shrinkage",
        )


@pytest.mark.asyncio
async def test_positive_adjustment_publishes_event(
    stock_engine_fixture: StockEngineFixture,
) -> None:
    """Positive adjustment creates a movement and publishes an event."""
    movement = await stock_engine_fixture.engine.adjust_stock(
        business_id=stock_engine_fixture.business_id,
        product_id=stock_engine_fixture.product_id,
        warehouse_id=stock_engine_fixture.warehouse_id,
        quantity_delta=Decimal("2.0000"),
        reason="Opening stock",
    )

    assert movement.movement_type == MovementType.ADJUSTMENT
    assert balance_for(stock_engine_fixture).quantity_on_hand == Decimal("2.0000")
    assert any(
        isinstance(event, StockAdjustedEvent)
        for event in stock_engine_fixture.dispatcher.events
    )


@pytest.mark.asyncio
async def test_transfer_stock_updates_both_warehouses(
    stock_engine_fixture: StockEngineFixture,
) -> None:
    """Stock transfer creates OUT and IN movements in one transaction."""
    await stock_engine_fixture.engine.receive_purchase(
        source_document(stock_engine_fixture, quantity=Decimal("10.0000"))
    )

    movements = await stock_engine_fixture.engine.transfer_stock(
        business_id=stock_engine_fixture.business_id,
        product_id=stock_engine_fixture.product_id,
        from_warehouse_id=stock_engine_fixture.warehouse_id,
        to_warehouse_id=stock_engine_fixture.second_warehouse_id,
        quantity=Decimal("4.0000"),
        notes="Move to auxiliary warehouse",
    )

    assert len(movements) == TRANSFER_MOVEMENT_COUNT
    assert balance_for(stock_engine_fixture).quantity_on_hand == Decimal("6.0000")
    assert (
        balance_for(
            stock_engine_fixture,
            stock_engine_fixture.second_warehouse_id,
        ).quantity_on_hand
        == Decimal("4.0000")
    )
    assert any(
        isinstance(event, StockTransferredEvent)
        for event in stock_engine_fixture.dispatcher.events
    )


@pytest.mark.asyncio
async def test_reserve_and_release_keep_available_quantity_consistent(
    stock_engine_fixture: StockEngineFixture,
) -> None:
    """Reservation changes reserved and available quantities only."""
    await stock_engine_fixture.engine.receive_purchase(
        source_document(stock_engine_fixture, quantity=Decimal("10.0000"))
    )

    await stock_engine_fixture.engine.reserve_stock(
        business_id=stock_engine_fixture.business_id,
        product_id=stock_engine_fixture.product_id,
        warehouse_id=stock_engine_fixture.warehouse_id,
        quantity=Decimal("4.0000"),
    )
    await stock_engine_fixture.engine.release_reservation(
        business_id=stock_engine_fixture.business_id,
        product_id=stock_engine_fixture.product_id,
        warehouse_id=stock_engine_fixture.warehouse_id,
        quantity=Decimal("2.0000"),
    )

    balance = balance_for(stock_engine_fixture)
    assert balance.quantity_on_hand == Decimal("10.0000")
    assert balance.quantity_reserved == Decimal("2.0000")
    assert balance.quantity_available == Decimal("8.0000")
    assert any(
        isinstance(event, StockReservedEvent)
        for event in stock_engine_fixture.dispatcher.events
    )
    assert any(
        isinstance(event, StockReleasedEvent)
        for event in stock_engine_fixture.dispatcher.events
    )


@pytest.mark.asyncio
async def test_issue_sale_prevents_negative_stock(
    stock_engine_fixture: StockEngineFixture,
) -> None:
    """Sale issue rejects stock quantities that are unavailable."""
    await stock_engine_fixture.engine.receive_purchase(
        source_document(stock_engine_fixture, quantity=Decimal("1.0000"))
    )

    with pytest.raises(NegativeStockException):
        await stock_engine_fixture.engine.issue_sale(
            source_document(stock_engine_fixture, quantity=Decimal("2.0000"))
        )

    assert stock_engine_fixture.uow.rolled_back is True


@pytest.mark.asyncio
async def test_transaction_rolls_back_when_balance_update_fails(
    stock_engine_fixture: StockEngineFixture,
) -> None:
    """A failing balance update rolls back the stock transaction."""
    stock_engine_fixture.uow.stock_balances.fail_update = True

    with pytest.raises(RuntimeError, match="forced stock balance failure"):
        await stock_engine_fixture.engine.receive_purchase(
            source_document(stock_engine_fixture, quantity=Decimal("5.0000"))
        )

    assert stock_engine_fixture.uow.rolled_back is True
    assert stock_engine_fixture.uow.committed is False


@pytest.mark.asyncio
async def test_missing_product_mapping_is_rejected(
    stock_engine_fixture: StockEngineFixture,
) -> None:
    """Stock source lines must carry explicit product identifiers."""
    document = SourceDocument(
        id=uuid.uuid4(),
        business_id=stock_engine_fixture.business_id,
        lines=[
            SourceLine(
                product_id=stock_engine_fixture.product_id,
                warehouse_id=stock_engine_fixture.warehouse_id,
                quantity=Decimal("1.0000"),
            )
        ],
    )
    delattr(document.lines[0], "product_id")

    with pytest.raises(InventoryValidationException):
        await stock_engine_fixture.engine.receive_purchase(document)
