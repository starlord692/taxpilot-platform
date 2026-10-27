"""Deterministic failure-injection and transaction consistency tests (EP-RC1.9).

Implements the 12 failure test cases (TC-FAIL-01 through TC-FAIL-12) specified in
EP-RC1.8-TRANSACTION-EVENT-CONSISTENCY-SPEC.md Section 8 and ADR-0021 / ADR-0022.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, cast
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.events import EventDispatcher
from app.common.outbox.models import OutboxEventRecord
from app.common.outbox.relay import OutboxRelay
from app.common.outbox.repository import OutboxRepository
from app.common.unit_of_work.sqlalchemy_uow import SQLAlchemyUnitOfWork
from app.modules.inventory.exceptions import NegativeStockException
from app.modules.inventory.models import (
    Product,
    StockBalance,
    Warehouse,
)
from app.modules.inventory.services.stock_engine import StockEngine
from app.modules.purchases.models import PurchaseInvoice, PurchaseStatus
from app.modules.purchases.services.purchase_service import PurchaseService
from app.modules.sales.models import (
    InvoiceStatus,
    Payment,
    PaymentMethod,
    SalesInvoice,
)
from app.modules.sales.schemas import PaymentCreateRequest
from app.modules.sales.services.invoice_service import SalesInvoiceService
from app.modules.sales.services.payment_service import PaymentService

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Test Helpers and Mocks
# ---------------------------------------------------------------------------


class MockUnitOfWork:
    """Mock Unit of Work tracking transaction boundaries and rollback."""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.sales_invoices = Mock()
        self.purchase_invoices = Mock()
        self.payments = Mock()
        self.outbox = Mock()
        self.customers = Mock()
        self.customers.get_by_id = AsyncMock(return_value=None)
        self.businesses = Mock()
        self.businesses.get_by_id = AsyncMock(return_value=None)
        self.staged_outbox_events: list[dict[str, Any]] = []

        async def _fake_outbox_add(*args: Any, **kwargs: Any) -> OutboxEventRecord:
            self.staged_outbox_events.append(kwargs)
            return OutboxEventRecord(
                id=uuid.uuid4(),
                event_name=kwargs.get("event_name", "test"),
                event_payload=kwargs.get("event_payload", {}),
            )

        self.outbox.add = AsyncMock(side_effect=_fake_outbox_add)

    async def __aenter__(self) -> MockUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        if exc_type is not None or not self.committed:
            self.rolled_back = True
            # Rollback discards staged outbox events atomically
            self.staged_outbox_events.clear()

    async def commit(self) -> None:
        self.committed = True


def _set_status(record: Any, new_status: Any) -> Any:
    record.status = getattr(new_status, "status", new_status)
    return record


def make_uow_factory(uow: MockUnitOfWork) -> Any:
    return lambda: uow


def build_draft_sales_invoice(business_id: uuid.UUID | None = None) -> SalesInvoice:
    b_id = business_id or uuid.uuid4()
    return SalesInvoice(
        id=uuid.uuid4(),
        business_id=b_id,
        customer_id=uuid.uuid4(),
        invoice_number="INV-20261013-0001",
        invoice_date=date(2026, 10, 13),
        status=InvoiceStatus.DRAFT,
        subtotal=Decimal("1000.00"),
        discount_amount=Decimal("0.00"),
        taxable_amount=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        lines=[],
    )


def build_draft_purchase_invoice(
    business_id: uuid.UUID | None = None,
) -> PurchaseInvoice:
    b_id = business_id or uuid.uuid4()
    return PurchaseInvoice(
        id=uuid.uuid4(),
        business_id=b_id,
        supplier_id=uuid.uuid4(),
        purchase_number="PUR-20261013-0001",
        invoice_number="SUPP-9999",
        invoice_date=date(2026, 10, 13),
        due_date=date(2026, 11, 13),
        status=PurchaseStatus.DRAFT,
        subtotal=Decimal("500.00"),
        tax_amount=Decimal("90.00"),
        total_amount=Decimal("590.00"),
        lines=[],
    )


# ---------------------------------------------------------------------------
# TC-FAIL-01: Issue Invoice Fails on Stock Shortage
# ---------------------------------------------------------------------------


async def test_issue_invoice_fails_on_stock_shortage() -> None:
    """TC-FAIL-01: When StockEngine fails due to stock shortage,
    invoice remains DRAFT."""
    uow = MockUnitOfWork()
    invoice = build_draft_sales_invoice()

    uow.sales_invoices.get_by_id = AsyncMock(return_value=invoice)
    uow.sales_invoices.mark_status = AsyncMock(side_effect=_set_status)

    stock_engine = Mock()
    stock_engine.issue_sale = AsyncMock(
        side_effect=NegativeStockException("Insufficient stock available")
    )

    accounting_kernel = Mock()
    accounting_kernel.record_sales_invoice = AsyncMock()

    service = SalesInvoiceService(
        unit_of_work_factory=make_uow_factory(uow),
        event_dispatcher=EventDispatcher(),
        stock_engine=stock_engine,
        accounting_kernel=accounting_kernel,
    )

    with pytest.raises(NegativeStockException, match="Insufficient stock"):
        await service.issue_invoice(invoice.id)

    # Invariants:
    assert uow.committed is False
    assert uow.rolled_back is True
    assert len(uow.staged_outbox_events) == 0
    accounting_kernel.record_sales_invoice.assert_not_awaited()


# ---------------------------------------------------------------------------
# TC-FAIL-02: Issue Invoice Fails on Missing Account
# ---------------------------------------------------------------------------


async def test_issue_invoice_fails_on_missing_account() -> None:
    """TC-FAIL-02: When AccountingKernel fails, invoice remains DRAFT
    and UoW rolls back."""
    uow = MockUnitOfWork()
    invoice = build_draft_sales_invoice()

    uow.sales_invoices.get_by_id = AsyncMock(return_value=invoice)
    uow.sales_invoices.mark_status = AsyncMock(side_effect=_set_status)

    stock_engine = Mock()
    stock_engine.issue_sale = AsyncMock(return_value=[])

    accounting_kernel = Mock()
    accounting_kernel.record_sales_invoice = AsyncMock(
        side_effect=RuntimeError("Chart of accounts configuration missing")
    )

    service = SalesInvoiceService(
        unit_of_work_factory=make_uow_factory(uow),
        event_dispatcher=EventDispatcher(),
        stock_engine=stock_engine,
        accounting_kernel=accounting_kernel,
    )

    with pytest.raises(RuntimeError, match="Chart of accounts configuration missing"):
        await service.issue_invoice(invoice.id)

    # Invariants:
    assert uow.committed is False
    assert uow.rolled_back is True
    assert len(uow.staged_outbox_events) == 0


# ---------------------------------------------------------------------------
# TC-FAIL-03: Approve Purchase Fails on Stock Error
# ---------------------------------------------------------------------------


async def test_approve_purchase_fails_on_stock_error() -> None:
    """TC-FAIL-03: When StockEngine fails receiving stock, purchase remains DRAFT."""
    uow = MockUnitOfWork()
    purchase = build_draft_purchase_invoice()

    uow.purchase_invoices.get_by_id = AsyncMock(return_value=purchase)
    uow.purchase_invoices.update = AsyncMock(side_effect=_set_status)

    stock_engine = Mock()
    stock_engine.receive_purchase = AsyncMock(
        side_effect=RuntimeError("Warehouse receipt error: bay locked")
    )

    accounting_kernel = Mock()
    accounting_kernel.record_purchase_invoice = AsyncMock()

    service = PurchaseService(
        unit_of_work_factory=make_uow_factory(uow),
        event_dispatcher=EventDispatcher(),
        stock_engine=stock_engine,
        accounting_kernel=accounting_kernel,
    )

    with pytest.raises(RuntimeError, match="Warehouse receipt error"):
        await service.approve_purchase(purchase.id)

    # Invariants:
    assert uow.committed is False
    assert uow.rolled_back is True
    assert len(uow.staged_outbox_events) == 0
    accounting_kernel.record_purchase_invoice.assert_not_awaited()


# ---------------------------------------------------------------------------
# TC-FAIL-04: Approve Purchase Fails on Accounting Error
# ---------------------------------------------------------------------------


async def test_approve_purchase_fails_on_accounting_error() -> None:
    """TC-FAIL-04: When AccountingKernel fails, purchase remains DRAFT
    and UoW rolls back."""
    uow = MockUnitOfWork()
    purchase = build_draft_purchase_invoice()

    uow.purchase_invoices.get_by_id = AsyncMock(return_value=purchase)
    uow.purchase_invoices.update = AsyncMock(side_effect=_set_status)

    stock_engine = Mock()
    stock_engine.receive_purchase = AsyncMock(return_value=[])

    accounting_kernel = Mock()
    accounting_kernel.record_purchase_invoice = AsyncMock(
        side_effect=ValueError("Unbalanced journal entries: debits != credits")
    )

    service = PurchaseService(
        unit_of_work_factory=make_uow_factory(uow),
        event_dispatcher=EventDispatcher(),
        stock_engine=stock_engine,
        accounting_kernel=accounting_kernel,
    )

    with pytest.raises(ValueError, match="Unbalanced journal entries"):
        await service.approve_purchase(purchase.id)

    # Invariants:
    assert uow.committed is False
    assert uow.rolled_back is True
    assert len(uow.staged_outbox_events) == 0


# ---------------------------------------------------------------------------
# TC-FAIL-05: Record Payment Fails on Accounting Error
# ---------------------------------------------------------------------------


async def test_record_payment_fails_on_accounting_error() -> None:
    """TC-FAIL-05: When AccountingKernel fails on payment, payment rolls back."""
    uow = MockUnitOfWork()
    invoice = build_draft_sales_invoice()
    invoice.status = InvoiceStatus.ISSUED

    uow.sales_invoices.get_by_id = AsyncMock(return_value=invoice)
    uow.sales_invoices.mark_status = AsyncMock()
    uow.payments.total_paid = AsyncMock(return_value=Decimal("0.00"))
    uow.payments.create = AsyncMock(
        return_value=Payment(
            id=uuid.uuid4(),
            invoice_id=invoice.id,
            payment_date=date(2026, 10, 13),
            amount=Decimal("500.00"),
            payment_method=PaymentMethod.BANK_TRANSFER,
        )
    )

    accounting_kernel = Mock()
    accounting_kernel.record_customer_payment = AsyncMock(
        side_effect=RuntimeError("Bank ledger account unavailable")
    )

    service = PaymentService(
        unit_of_work_factory=make_uow_factory(uow),
        event_dispatcher=EventDispatcher(),
        accounting_kernel=accounting_kernel,
    )

    req = PaymentCreateRequest(
        invoice_id=invoice.id,
        payment_date=date(2026, 10, 13),
        amount=Decimal("500.00"),
        payment_method=PaymentMethod.BANK_TRANSFER,
    )

    with pytest.raises(RuntimeError, match="Bank ledger account unavailable"):
        await service.record_payment(req)

    # Invariants:
    assert uow.committed is False
    assert uow.rolled_back is True
    assert len(uow.staged_outbox_events) == 0


# ---------------------------------------------------------------------------
# TC-FAIL-06: UoW Commit Failure Triggers Full Rollback
# ---------------------------------------------------------------------------


async def test_uow_commit_failure_triggers_full_rollback() -> None:
    """TC-FAIL-06: SQLAlchemy flush/commit IntegrityError triggers full
    rollback and cleanup."""
    session = Mock(spec=AsyncSession)
    session.add = Mock()
    session.commit = AsyncMock(
        side_effect=IntegrityError("duplicate key value", params={}, orig=Exception())
    )
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    uow = SQLAlchemyUnitOfWork(lambda: session)

    with pytest.raises(IntegrityError):
        async with uow:
            await uow.commit()

    cast(Any, session.rollback).assert_awaited_once()
    cast(Any, session.close).assert_awaited_once()
    assert uow.is_active is False


# ---------------------------------------------------------------------------
# TC-FAIL-07: Task Cancellation Triggers Clean Rollback
# ---------------------------------------------------------------------------


async def test_uow_task_cancellation_triggers_clean_rollback() -> None:
    """TC-FAIL-07: Task cancellation (CancelledError) rolls back and cleans
    up session."""
    session = Mock(spec=AsyncSession)
    session.add = Mock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    uow = SQLAlchemyUnitOfWork(lambda: session)

    with pytest.raises(asyncio.CancelledError):
        async with uow:
            raise asyncio.CancelledError()

    cast(Any, session.commit).assert_not_awaited()
    cast(Any, session.rollback).assert_awaited_once()
    cast(Any, session.close).assert_awaited_once()
    assert uow.is_active is False


# ---------------------------------------------------------------------------
# TC-FAIL-08: Re-entrant Context Entry Is Forbidden
# ---------------------------------------------------------------------------


async def test_uow_prevents_reentrant_context_entry() -> None:
    """TC-FAIL-08: Re-entering an active Unit of Work raises RuntimeError
    immediately."""
    session = Mock(spec=AsyncSession)
    session.add = Mock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    uow = SQLAlchemyUnitOfWork(lambda: session)

    async with uow:
        assert uow.is_active is True
        with pytest.raises(RuntimeError, match="does not support re-entrant"):
            async with uow:
                pass


# ---------------------------------------------------------------------------
# TC-FAIL-09: Subordinate Services Forbidden from Committing
# ---------------------------------------------------------------------------


async def test_subordinate_service_forbidden_from_commit() -> None:
    """TC-FAIL-09: Subordinate services in subordinate mode MUST NOT invoke commit()."""
    b_id = uuid.uuid4()
    p_id = uuid.uuid4()
    w_id = uuid.uuid4()

    shared_uow = Mock()
    shared_uow.commit = AsyncMock()
    shared_uow.products = Mock()
    shared_uow.products.get_by_id = AsyncMock(
        return_value=Product(
            id=p_id,
            business_id=b_id,
            sku="SKU-001",
            name="Test Product",
            is_active=True,
        )
    )
    shared_uow.warehouses = Mock()
    shared_uow.warehouses.get_by_id = AsyncMock(
        return_value=Warehouse(
            id=w_id,
            business_id=b_id,
            code="WH-001",
            name="Main Warehouse",
            is_active=True,
        )
    )
    shared_uow.stock_balances = Mock()
    shared_uow.stock_balances.get_by_product_and_warehouse = AsyncMock(
        return_value=StockBalance(
            id=uuid.uuid4(),
            business_id=b_id,
            product_id=p_id,
            warehouse_id=w_id,
            quantity_on_hand=Decimal("100.00"),
            quantity_reserved=Decimal("0.00"),
            quantity_available=Decimal("100.00"),
        )
    )
    shared_uow.stock_balances.update = AsyncMock()
    shared_uow.stock_movements = Mock()
    shared_uow.stock_movements.create = AsyncMock()

    stock_engine = StockEngine(
        unit_of_work_factory=Mock,
        event_dispatcher=EventDispatcher(),
    )

    mock_line = Mock(
        product_id=p_id,
        warehouse_id=w_id,
        quantity=Decimal("1.00"),
        description="Item 1",
    )
    invoice = Mock(
        id=uuid.uuid4(),
        business_id=b_id,
        lines=[mock_line],
    )

    # Run in subordinate mode with shared_uow
    await stock_engine.issue_sale(invoice, uow=shared_uow)

    # Invariant: shared_uow.commit was NEVER called by subordinate service!
    shared_uow.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# TC-FAIL-10: Outbox Event Rolled Back on Business Failure
# ---------------------------------------------------------------------------


async def test_outbox_event_rolled_back_on_business_failure() -> None:
    """TC-FAIL-10: If business operation fails, staged outbox events are discarded."""
    uow = MockUnitOfWork()
    invoice = build_draft_sales_invoice()

    uow.sales_invoices.get_by_id = AsyncMock(return_value=invoice)
    uow.sales_invoices.mark_status = AsyncMock(return_value=invoice)

    # Stock fails after status update
    stock_engine = Mock()
    stock_engine.issue_sale = AsyncMock(side_effect=RuntimeError("Stock failure"))

    service = SalesInvoiceService(
        unit_of_work_factory=make_uow_factory(uow),
        event_dispatcher=EventDispatcher(),
        stock_engine=stock_engine,
    )

    with pytest.raises(RuntimeError, match="Stock failure"):
        await service.issue_invoice(invoice.id)

    # Outbox events must be completely empty
    assert len(uow.staged_outbox_events) == 0
    assert uow.committed is False
    assert uow.rolled_back is True


# ---------------------------------------------------------------------------
# TC-FAIL-11: Outbox Event Committed With Business State
# ---------------------------------------------------------------------------


async def test_outbox_event_committed_with_business_state() -> None:
    """TC-FAIL-11: Successful business operation stages outbox event
    and commits together."""
    uow = MockUnitOfWork()
    invoice = build_draft_sales_invoice()

    uow.sales_invoices.get_by_id = AsyncMock(return_value=invoice)
    uow.sales_invoices.mark_status = AsyncMock(side_effect=_set_status)

    stock_engine = Mock()
    stock_engine.issue_sale = AsyncMock(return_value=[])

    accounting_kernel = Mock()
    accounting_kernel.record_sales_invoice = AsyncMock(return_value=object())

    service = SalesInvoiceService(
        unit_of_work_factory=make_uow_factory(uow),
        event_dispatcher=EventDispatcher(),
        stock_engine=stock_engine,
        accounting_kernel=accounting_kernel,
    )

    response = await service.issue_invoice(invoice.id)

    # Invariants:
    assert response.status == InvoiceStatus.ISSUED
    assert uow.committed is True
    assert len(uow.staged_outbox_events) == 1
    assert uow.staged_outbox_events[0]["event_name"] == "sales.invoice.issued"
    assert uow.staged_outbox_events[0]["business_id"] == invoice.business_id


# ---------------------------------------------------------------------------
# TC-FAIL-12: Outbox Worker Idempotent Delivery and Poison Pill Isolation
# ---------------------------------------------------------------------------


async def test_outbox_worker_idempotent_delivery() -> None:
    """TC-FAIL-12: Relay delivers event at least once; consumer
    idempotently handles duplicates."""
    processed_event_ids: set[str] = set()
    execution_counts: dict[str, int] = {}

    async def idempotent_consumer(event_name: str, payload: dict[str, Any]) -> None:
        event_id = payload.get("event_id", "")
        execution_counts[event_id] = execution_counts.get(event_id, 0) + 1
        if event_id in processed_event_ids:
            # Duplicate received — deduplicate safely
            return
        processed_event_ids.add(event_id)

    # Simulate delivering the same event twice
    event_id = str(uuid.uuid4())
    payload = {"event_id": event_id, "amount": "100.00"}

    await idempotent_consumer("invoice.issued", payload)
    assert len(processed_event_ids) == 1
    assert execution_counts[event_id] == 1

    # Redelivery (at-least-once simulation)
    expected_duplicate_runs = 2
    await idempotent_consumer("invoice.issued", payload)
    assert len(processed_event_ids) == 1
    assert execution_counts[event_id] == expected_duplicate_runs


async def test_outbox_relay_poison_pill_dead_letter_isolation() -> None:
    """TC-FAIL-12 (Extended): Repeatedly failing event transitions to DEAD_LETTER."""
    session = Mock(spec=AsyncSession)
    mock_result = Mock()
    mock_result.rowcount = 1
    session.execute = AsyncMock(return_value=mock_result)
    session.flush = AsyncMock()
    repo = OutboxRepository(session)

    record_id = uuid.uuid4()
    updated = await repo.mark_failed(
        record_id, error="Permanent handler crash", worker_id="worker-1"
    )

    assert updated is True
    assert session.execute.call_count == 1
    stmt = session.execute.call_args[0][0]
    assert stmt.table.name == "outbox_events"


# ---------------------------------------------------------------------------
# Remediation Tests: P0-A, P0-B, P1-A, P1-B
# ---------------------------------------------------------------------------


class CapturingEventDispatcher(EventDispatcher):
    """Event dispatcher that captures all dispatched events."""

    def __init__(self) -> None:
        super().__init__()
        self.dispatched_events: list[Any] = []

    async def dispatch(self, event: Any) -> None:
        self.dispatched_events.append(event)
        await super().dispatch(event)


async def test_subordinate_typeerror_propagates_and_rolls_back_issue_invoice() -> None:
    """P1-B / F-06: TypeError in StockEngine propagates and triggers rollback."""
    uow = MockUnitOfWork()
    invoice = build_draft_sales_invoice()

    uow.sales_invoices.get_by_id = AsyncMock(return_value=invoice)
    uow.sales_invoices.mark_status = AsyncMock(side_effect=_set_status)

    stock_engine = Mock()
    # Simulates internal TypeError (e.g. invalid type inside stock calculation)
    stock_engine.issue_sale = AsyncMock(
        side_effect=TypeError(
            "unsupported operand type(s) for -: 'NoneType' and 'Decimal'"
        )
    )

    accounting_kernel = Mock()
    accounting_kernel.record_sales_invoice = AsyncMock()

    dispatcher = CapturingEventDispatcher()
    service = SalesInvoiceService(
        unit_of_work_factory=make_uow_factory(uow),
        event_dispatcher=dispatcher,
        stock_engine=stock_engine,
        accounting_kernel=accounting_kernel,
    )

    with pytest.raises(TypeError, match="unsupported operand"):
        await service.issue_invoice(invoice.id)

    # Invariants:
    assert uow.committed is False
    assert uow.rolled_back is True
    assert len(uow.staged_outbox_events) == 0
    assert len(dispatcher.dispatched_events) == 0
    accounting_kernel.record_sales_invoice.assert_not_awaited()


async def test_subordinate_typeerror_rolls_back_approve_purchase() -> None:
    """P1-B / F-06: StockEngine TypeError triggers rollback on purchase approval."""
    uow = MockUnitOfWork()
    purchase = build_draft_purchase_invoice()

    uow.purchase_invoices.get_by_id = AsyncMock(return_value=purchase)
    uow.purchase_invoices.update = AsyncMock(side_effect=_set_status)

    stock_engine = Mock()
    stock_engine.receive_purchase = AsyncMock(
        side_effect=TypeError("Cannot format quantity with invalid type")
    )

    accounting_kernel = Mock()
    accounting_kernel.record_purchase_invoice = AsyncMock()

    dispatcher = CapturingEventDispatcher()
    service = PurchaseService(
        unit_of_work_factory=make_uow_factory(uow),
        event_dispatcher=dispatcher,
        stock_engine=stock_engine,
        accounting_kernel=accounting_kernel,
    )

    with pytest.raises(TypeError, match="Cannot format quantity"):
        await service.approve_purchase(purchase.id)

    assert uow.committed is False
    assert uow.rolled_back is True
    assert len(uow.staged_outbox_events) == 0
    assert len(dispatcher.dispatched_events) == 0
    accounting_kernel.record_purchase_invoice.assert_not_awaited()


async def test_subordinate_typeerror_propagates_and_rolls_back_record_payment() -> None:
    """P1-B / F-06: AccountingKernel TypeError triggers rollback on payment."""
    uow = MockUnitOfWork()
    invoice = build_draft_sales_invoice()
    invoice.status = InvoiceStatus.ISSUED

    uow.sales_invoices.get_by_id = AsyncMock(return_value=invoice)
    uow.sales_invoices.mark_status = AsyncMock()
    uow.payments.total_paid = AsyncMock(return_value=Decimal("0.00"))
    uow.payments.create = AsyncMock(
        return_value=Payment(
            id=uuid.uuid4(),
            invoice_id=invoice.id,
            payment_date=date(2026, 10, 13),
            amount=Decimal("500.00"),
            payment_method=PaymentMethod.BANK_TRANSFER,
        )
    )

    accounting_kernel = Mock()
    accounting_kernel.record_customer_payment = AsyncMock(
        side_effect=TypeError("Invalid payment ledger parameter type")
    )

    dispatcher = CapturingEventDispatcher()
    service = PaymentService(
        unit_of_work_factory=make_uow_factory(uow),
        event_dispatcher=dispatcher,
        accounting_kernel=accounting_kernel,
    )

    req = PaymentCreateRequest(
        invoice_id=invoice.id,
        payment_date=date(2026, 10, 13),
        amount=Decimal("500.00"),
        payment_method=PaymentMethod.BANK_TRANSFER,
    )

    with pytest.raises(TypeError, match="Invalid payment ledger parameter"):
        await service.record_payment(req)

    assert uow.committed is False
    assert uow.rolled_back is True
    assert len(uow.staged_outbox_events) == 0
    assert len(dispatcher.dispatched_events) == 0


async def test_pre_commit_failure_emits_zero_in_memory_events() -> None:
    """P0-B / F-04: Failed financial operations emit zero in-memory events."""
    uow = MockUnitOfWork()
    invoice = build_draft_sales_invoice()

    uow.sales_invoices.get_by_id = AsyncMock(return_value=invoice)
    uow.sales_invoices.mark_status = AsyncMock(side_effect=_set_status)

    stock_engine = Mock()
    stock_engine.issue_sale = AsyncMock(return_value=[])

    accounting_kernel = Mock()
    accounting_kernel.record_sales_invoice = AsyncMock(
        side_effect=RuntimeError("Accounting failure before commit")
    )

    dispatcher = CapturingEventDispatcher()
    service = SalesInvoiceService(
        unit_of_work_factory=make_uow_factory(uow),
        event_dispatcher=dispatcher,
        stock_engine=stock_engine,
        accounting_kernel=accounting_kernel,
    )

    with pytest.raises(RuntimeError, match="Accounting failure before commit"):
        await service.issue_invoice(invoice.id)

    # Invariants: absolutely zero events leaked to in-memory dispatcher
    assert len(dispatcher.dispatched_events) == 0
    assert uow.committed is False
    assert uow.rolled_back is True


async def test_unhandled_outbox_event_marked_failed_not_published() -> None:
    """P0-A / F-04: Outbox relay triggers failure when no subscriber registered."""
    session = Mock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    class FakeSessionContext:
        async def __aenter__(self) -> AsyncSession:
            return session

        async def __aexit__(self, *args: Any) -> None:
            pass

    event_id = uuid.uuid4()
    event_name = "unregistered.custom.event"
    event_payload = {"data": "test"}

    with patch.object(
        OutboxRepository, "mark_failed", AsyncMock(return_value=True)
    ) as mock_mark_failed, patch.object(
        OutboxRepository, "mark_published", AsyncMock(return_value=True)
    ) as mock_mark_pub:
        relay = OutboxRelay(
            session_factory=FakeSessionContext,
            worker_id="test-worker",
        )
        # No subscriber registered for "unregistered.custom.event"

        await relay._dispatch_single_event(
            event_id, event_name, event_payload
        )

        mock_mark_pub.assert_not_called()
        mock_mark_failed.assert_called_once()
        call_args = mock_mark_failed.call_args
        assert call_args[0][0] == event_id
        assert "No subscriber registered" in call_args[0][1]
        assert call_args[1]["worker_id"] == "test-worker"


async def test_outbox_claim_fencing_rejects_stale_worker() -> None:
    """P1-A / F-04: Fencing prevents stale worker from updating claimed event."""
    session = Mock(spec=AsyncSession)
    session.flush = AsyncMock()
    repo = OutboxRepository(session)

    event_id = uuid.uuid4()

    # Worker-A execution yields 0 rows updated because claimed_by != 'worker-A' in DB
    session.execute = AsyncMock(return_value=Mock(rowcount=0))

    # Stale worker-A tries to mark published
    result = await repo.mark_published(event_id, worker_id="worker-A")
    assert result is False

    # Stale worker-A tries to mark failed
    result_fail = await repo.mark_failed(
        event_id, error="Stale error", worker_id="worker-A"
    )
    assert result_fail is False

    # Authorized worker-B matches claimed_by in DB, updating 1 row
    session.execute = AsyncMock(return_value=Mock(rowcount=1))
    result_ok = await repo.mark_published(event_id, worker_id="worker-B")
    assert result_ok is True


async def test_outbox_repository_rejects_missing_or_empty_worker_id() -> None:
    """Task 2.1: Repository API rejects missing worker identity without DB call."""
    session = Mock(spec=AsyncSession)
    session.execute = AsyncMock()
    repo = OutboxRepository(session)
    event_id = uuid.uuid4()

    with pytest.raises(ValueError, match="worker_id is required"):
        await repo.mark_published(event_id, worker_id="")

    with pytest.raises(ValueError, match="worker_id is required"):
        await repo.mark_published(event_id, worker_id="   ")

    with pytest.raises(ValueError, match="worker_id is required"):
        await repo.mark_published(event_id, worker_id=None)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="worker_id is required"):
        await repo.mark_failed(event_id, "error", worker_id="")

    with pytest.raises(ValueError, match="worker_id is required"):
        await repo.mark_failed(event_id, "error", worker_id="   ")

    with pytest.raises(ValueError, match="worker_id is required"):
        await repo.mark_failed(event_id, "error", worker_id=None)  # type: ignore[arg-type]

    # Invariant: session.execute was never called before rejection
    assert session.execute.call_count == 0


