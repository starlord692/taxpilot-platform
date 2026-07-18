"""Stock movement engine for inventory projections."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from app.common.events import EventDispatcher
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
    ProductNotFoundException,
    WarehouseNotFoundException,
)
from app.modules.inventory.models import MovementType, Product, StockBalance
from app.modules.inventory.models.stock_movement import StockMovement
from app.modules.inventory.models.warehouse import Warehouse
from app.modules.inventory.schemas import StockMovementCreate

ZERO_QUANTITY = Decimal("0.0000")


@dataclass(frozen=True)
class StockLine:
    """Normalized source line for stock movement processing."""

    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    quantity: Decimal
    description: str | None = None


class StockProductRepository(Protocol):
    """Product repository behavior required by the stock engine."""

    async def get_by_id(self, product_id: uuid.UUID) -> Product | None:
        """Return a product by UUID."""
        ...


class StockWarehouseRepository(Protocol):
    """Warehouse repository behavior required by the stock engine."""

    async def get_by_id(self, warehouse_id: uuid.UUID) -> Warehouse | None:
        """Return a warehouse by UUID."""
        ...


class StockBalanceProjectionRepository(Protocol):
    """Stock balance repository behavior required by the stock engine."""

    async def create(
        self,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        quantity_on_hand: Decimal = ZERO_QUANTITY,
        quantity_reserved: Decimal = ZERO_QUANTITY,
        quantity_available: Decimal = ZERO_QUANTITY,
    ) -> StockBalance:
        """Create a stock balance projection row."""
        ...

    async def update(
        self,
        balance: StockBalance,
        *,
        quantity_on_hand: Decimal | None = None,
        quantity_reserved: Decimal | None = None,
        quantity_available: Decimal | None = None,
    ) -> StockBalance:
        """Update a stock balance projection row."""
        ...

    async def get_by_product_and_warehouse(
        self,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
    ) -> StockBalance | None:
        """Return one product and warehouse stock balance."""
        ...


class StockMovementPersistenceRepository(Protocol):
    """Stock movement repository behavior required by the stock engine."""

    async def create(
        self,
        request: StockMovementCreate,
        *,
        business_id: uuid.UUID,
    ) -> StockMovement:
        """Create an immutable stock movement."""
        ...


class StockEngineUnitOfWork(Protocol):
    """Unit of Work contract required by stock movement operations."""

    products: StockProductRepository
    warehouses: StockWarehouseRepository
    stock_balances: StockBalanceProjectionRepository
    stock_movements: StockMovementPersistenceRepository

    async def __aenter__(self) -> StockEngineUnitOfWork:
        """Enter the inventory transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the inventory transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit inventory changes."""
        ...


UnitOfWorkFactory = Callable[[], StockEngineUnitOfWork]


class StockEngine:
    """Create immutable stock movements and maintain stock balances."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
        allow_negative_stock: bool = False,
    ) -> None:
        """Initialize stock engine dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher
        self._allow_negative_stock = allow_negative_stock

    async def receive_purchase(
        self,
        purchase_invoice: Any,
        *,
        warehouse_id: uuid.UUID | None = None,
    ) -> list[StockMovement]:
        """Receive purchase invoice lines into stock."""
        business_id = self._source_business_id(purchase_invoice)
        source_id = self._source_id(purchase_invoice)
        lines = self._source_lines(purchase_invoice, warehouse_id)
        async with self._unit_of_work_factory() as uow:
            movements = await self._apply_source_lines(
                uow,
                business_id=business_id,
                source_id=source_id,
                source_type="purchase_invoice",
                lines=lines,
                movement_type=MovementType.PURCHASE,
                on_hand_multiplier=Decimal("1"),
            )
            await self._event_dispatcher.dispatch(
                StockReceivedEvent(
                    business_id=business_id,
                    source_id=source_id,
                    movement_ids=tuple(movement.id for movement in movements),
                )
            )
            await uow.commit()
        return movements

    async def issue_sale(
        self,
        sales_invoice: Any,
        *,
        warehouse_id: uuid.UUID | None = None,
    ) -> list[StockMovement]:
        """Issue sales invoice lines from stock."""
        business_id = self._source_business_id(sales_invoice)
        source_id = self._source_id(sales_invoice)
        lines = self._source_lines(sales_invoice, warehouse_id)
        async with self._unit_of_work_factory() as uow:
            movements = await self._apply_source_lines(
                uow,
                business_id=business_id,
                source_id=source_id,
                source_type="sales_invoice",
                lines=lines,
                movement_type=MovementType.SALE,
                on_hand_multiplier=Decimal("-1"),
            )
            await self._event_dispatcher.dispatch(
                StockIssuedEvent(
                    business_id=business_id,
                    source_id=source_id,
                    movement_ids=tuple(movement.id for movement in movements),
                )
            )
            await uow.commit()
        return movements

    async def return_sale(
        self,
        sales_invoice: Any,
        *,
        warehouse_id: uuid.UUID | None = None,
    ) -> list[StockMovement]:
        """Return previously sold stock to inventory."""
        business_id = self._source_business_id(sales_invoice)
        source_id = self._source_id(sales_invoice)
        lines = self._source_lines(sales_invoice, warehouse_id)
        async with self._unit_of_work_factory() as uow:
            movements = await self._apply_source_lines(
                uow,
                business_id=business_id,
                source_id=source_id,
                source_type="sales_return",
                lines=lines,
                movement_type=MovementType.RETURN,
                on_hand_multiplier=Decimal("1"),
            )
            await uow.commit()
        return movements

    async def return_purchase(
        self,
        purchase_invoice: Any,
        *,
        warehouse_id: uuid.UUID | None = None,
    ) -> list[StockMovement]:
        """Return purchased stock to a supplier."""
        business_id = self._source_business_id(purchase_invoice)
        source_id = self._source_id(purchase_invoice)
        lines = self._source_lines(purchase_invoice, warehouse_id)
        async with self._unit_of_work_factory() as uow:
            movements = await self._apply_source_lines(
                uow,
                business_id=business_id,
                source_id=source_id,
                source_type="purchase_return",
                lines=lines,
                movement_type=MovementType.RETURN,
                on_hand_multiplier=Decimal("-1"),
            )
            await uow.commit()
        return movements

    async def adjust_stock(
        self,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        quantity_delta: Decimal,
        reason: str,
    ) -> StockMovement:
        """Apply a positive or negative stock adjustment."""
        if not reason.strip():
            raise InventoryValidationException("Stock adjustment reason is required")
        if quantity_delta == ZERO_QUANTITY:
            raise InventoryValidationException(
                "Stock adjustment quantity cannot be zero"
            )

        async with self._unit_of_work_factory() as uow:
            await self._apply_balance_delta(
                uow,
                business_id=business_id,
                product_id=product_id,
                warehouse_id=warehouse_id,
                on_hand_delta=quantity_delta,
            )
            movement = await self._create_movement(
                uow,
                business_id=business_id,
                product_id=product_id,
                warehouse_id=warehouse_id,
                movement_type=MovementType.ADJUSTMENT,
                quantity=abs(quantity_delta),
                reference_type="inventory_adjustment",
                reference_id=uuid.uuid4(),
                notes=reason,
            )
            await self._event_dispatcher.dispatch(
                StockAdjustedEvent(
                    business_id=business_id,
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    movement_id=movement.id,
                )
            )
            await uow.commit()
        return movement

    async def transfer_stock(
        self,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
        from_warehouse_id: uuid.UUID,
        to_warehouse_id: uuid.UUID,
        quantity: Decimal,
        notes: str | None = None,
    ) -> list[StockMovement]:
        """Transfer stock between two warehouses in one transaction."""
        self._ensure_positive_quantity(quantity)
        if from_warehouse_id == to_warehouse_id:
            raise InventoryValidationException(
                "Transfer warehouses must be different",
                details={"warehouse_id": str(from_warehouse_id)},
            )

        transfer_id = uuid.uuid4()
        async with self._unit_of_work_factory() as uow:
            await self._apply_balance_delta(
                uow,
                business_id=business_id,
                product_id=product_id,
                warehouse_id=from_warehouse_id,
                on_hand_delta=-quantity,
            )
            await self._apply_balance_delta(
                uow,
                business_id=business_id,
                product_id=product_id,
                warehouse_id=to_warehouse_id,
                on_hand_delta=quantity,
            )
            out_movement = await self._create_movement(
                uow,
                business_id=business_id,
                product_id=product_id,
                warehouse_id=from_warehouse_id,
                movement_type=MovementType.TRANSFER,
                quantity=quantity,
                reference_type="inventory_transfer_out",
                reference_id=transfer_id,
                notes=notes,
            )
            in_movement = await self._create_movement(
                uow,
                business_id=business_id,
                product_id=product_id,
                warehouse_id=to_warehouse_id,
                movement_type=MovementType.TRANSFER,
                quantity=quantity,
                reference_type="inventory_transfer_in",
                reference_id=transfer_id,
                notes=notes,
            )
            movements = [out_movement, in_movement]
            await self._event_dispatcher.dispatch(
                StockTransferredEvent(
                    business_id=business_id,
                    product_id=product_id,
                    from_warehouse_id=from_warehouse_id,
                    to_warehouse_id=to_warehouse_id,
                    movement_ids=tuple(movement.id for movement in movements),
                )
            )
            await uow.commit()
        return movements

    async def reserve_stock(
        self,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        quantity: Decimal,
        reference_id: uuid.UUID | None = None,
    ) -> StockBalance:
        """Reserve available stock without changing on-hand quantity."""
        self._ensure_positive_quantity(quantity)
        async with self._unit_of_work_factory() as uow:
            balance = await self._apply_balance_delta(
                uow,
                business_id=business_id,
                product_id=product_id,
                warehouse_id=warehouse_id,
                reserved_delta=quantity,
            )
            await self._event_dispatcher.dispatch(
                StockReservedEvent(
                    business_id=business_id,
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    quantity=quantity,
                    reference_id=reference_id,
                )
            )
            await uow.commit()
        return balance

    async def release_reservation(
        self,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        quantity: Decimal,
        reference_id: uuid.UUID | None = None,
    ) -> StockBalance:
        """Release reserved stock and increase available quantity."""
        self._ensure_positive_quantity(quantity)
        async with self._unit_of_work_factory() as uow:
            balance = await self._apply_balance_delta(
                uow,
                business_id=business_id,
                product_id=product_id,
                warehouse_id=warehouse_id,
                reserved_delta=-quantity,
            )
            await self._event_dispatcher.dispatch(
                StockReleasedEvent(
                    business_id=business_id,
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    quantity=quantity,
                    reference_id=reference_id,
                )
            )
            await uow.commit()
        return balance

    async def _apply_source_lines(
        self,
        uow: StockEngineUnitOfWork,
        *,
        business_id: uuid.UUID,
        source_id: uuid.UUID,
        source_type: str,
        lines: Iterable[StockLine],
        movement_type: MovementType,
        on_hand_multiplier: Decimal,
    ) -> list[StockMovement]:
        """Apply stock lines and return the created movements."""
        movements: list[StockMovement] = []
        for line in lines:
            self._ensure_positive_quantity(line.quantity)
            await self._apply_balance_delta(
                uow,
                business_id=business_id,
                product_id=line.product_id,
                warehouse_id=line.warehouse_id,
                on_hand_delta=line.quantity * on_hand_multiplier,
            )
            movements.append(
                await self._create_movement(
                    uow,
                    business_id=business_id,
                    product_id=line.product_id,
                    warehouse_id=line.warehouse_id,
                    movement_type=movement_type,
                    quantity=line.quantity,
                    reference_type=source_type,
                    reference_id=source_id,
                    notes=line.description,
                )
            )
        if not movements:
            raise InventoryValidationException("At least one stock line is required")
        return movements

    async def _apply_balance_delta(
        self,
        uow: StockEngineUnitOfWork,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        on_hand_delta: Decimal = ZERO_QUANTITY,
        reserved_delta: Decimal = ZERO_QUANTITY,
    ) -> StockBalance:
        """Apply projection deltas and keep available quantity consistent."""
        await self._validate_product(uow, business_id, product_id)
        await self._validate_warehouse(uow, business_id, warehouse_id)
        balance = await self._get_or_create_balance(
            uow,
            business_id=business_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
        )

        quantity_on_hand = balance.quantity_on_hand + on_hand_delta
        quantity_reserved = balance.quantity_reserved + reserved_delta
        quantity_available = quantity_on_hand - quantity_reserved
        self._ensure_quantities_allowed(
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=quantity_reserved,
            quantity_available=quantity_available,
        )
        return await uow.stock_balances.update(
            balance,
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=quantity_reserved,
            quantity_available=quantity_available,
        )

    async def _get_or_create_balance(
        self,
        uow: StockEngineUnitOfWork,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
    ) -> StockBalance:
        """Return an existing stock balance or create a zero projection."""
        balance = await uow.stock_balances.get_by_product_and_warehouse(
            business_id=business_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
        )
        if balance is not None:
            return balance
        return await uow.stock_balances.create(
            business_id=business_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
        )

    async def _create_movement(
        self,
        uow: StockEngineUnitOfWork,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        movement_type: MovementType,
        quantity: Decimal,
        reference_type: str,
        reference_id: uuid.UUID,
        notes: str | None,
    ) -> StockMovement:
        """Persist an immutable stock movement."""
        request = StockMovementCreate(
            product_id=product_id,
            warehouse_id=warehouse_id,
            movement_type=movement_type,
            quantity=quantity,
            reference_type=reference_type,
            reference_id=reference_id,
            notes=notes,
        )
        return await uow.stock_movements.create(request, business_id=business_id)

    async def _validate_product(
        self,
        uow: StockEngineUnitOfWork,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> None:
        """Validate that a product exists and belongs to the business."""
        product = await uow.products.get_by_id(product_id)
        if product is None or product.business_id != business_id:
            raise ProductNotFoundException(
                "Product not found",
                details={"product_id": str(product_id)},
            )
        if not product.is_active:
            raise InventoryValidationException(
                "Product is inactive",
                details={"product_id": str(product_id)},
            )

    async def _validate_warehouse(
        self,
        uow: StockEngineUnitOfWork,
        business_id: uuid.UUID,
        warehouse_id: uuid.UUID,
    ) -> None:
        """Validate that a warehouse exists and belongs to the business."""
        warehouse = await uow.warehouses.get_by_id(warehouse_id)
        if warehouse is None or warehouse.business_id != business_id:
            raise WarehouseNotFoundException(
                "Warehouse not found",
                details={"warehouse_id": str(warehouse_id)},
            )
        if not warehouse.is_active:
            raise InventoryValidationException(
                "Warehouse is inactive",
                details={"warehouse_id": str(warehouse_id)},
            )

    def _source_lines(
        self,
        source: Any,
        default_warehouse_id: uuid.UUID | None,
    ) -> list[StockLine]:
        """Normalize stock-relevant lines from a purchase or sales source."""
        raw_lines = getattr(source, "lines", None)
        if raw_lines is None:
            raise InventoryValidationException("Stock source does not contain lines")

        lines: list[StockLine] = []
        for raw_line in raw_lines:
            product_id = getattr(raw_line, "product_id", None)
            warehouse_id = (
                getattr(raw_line, "warehouse_id", None) or default_warehouse_id
            )
            if product_id is None:
                raise InventoryValidationException(
                    "Stock source line must include product_id"
                )
            if warehouse_id is None:
                raise InventoryValidationException(
                    "Stock source line must include warehouse_id"
                )
            lines.append(
                StockLine(
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    quantity=Decimal(str(raw_line.quantity)),
                    description=getattr(raw_line, "description", None),
                )
            )
        return lines

    def _source_business_id(self, source: Any) -> uuid.UUID:
        """Return a stock source business identifier."""
        business_id = getattr(source, "business_id", None)
        if not isinstance(business_id, uuid.UUID):
            raise InventoryValidationException("Stock source must include business_id")
        return business_id

    def _source_id(self, source: Any) -> uuid.UUID:
        """Return a stock source identifier."""
        source_id = getattr(source, "id", None)
        if not isinstance(source_id, uuid.UUID):
            raise InventoryValidationException("Stock source must include id")
        return source_id

    def _ensure_positive_quantity(self, quantity: Decimal) -> None:
        """Validate a positive stock quantity."""
        if quantity <= ZERO_QUANTITY:
            raise InventoryValidationException(
                "Stock movement quantity must be greater than zero",
                details={"quantity": str(quantity)},
            )

    def _ensure_quantities_allowed(
        self,
        *,
        quantity_on_hand: Decimal,
        quantity_reserved: Decimal,
        quantity_available: Decimal,
    ) -> None:
        """Validate stock projection quantities after a movement."""
        if quantity_reserved < ZERO_QUANTITY:
            raise InventoryValidationException(
                "Reserved stock cannot become negative",
                details={"quantity_reserved": str(quantity_reserved)},
            )
        if self._allow_negative_stock:
            return
        if quantity_on_hand < ZERO_QUANTITY or quantity_available < ZERO_QUANTITY:
            raise NegativeStockException(
                "Stock operation would create negative stock",
                details={
                    "quantity_on_hand": str(quantity_on_hand),
                    "quantity_available": str(quantity_available),
                },
            )
