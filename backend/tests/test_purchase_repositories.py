"""Tests for Purchase Management repositories."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.business.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
from app.common.filters import FilterCondition, FilterParams, SortCondition
from app.common.pagination import PaginationParams
from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.modules.purchases.models import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchaseStatus,
    Supplier,
)
from app.modules.purchases.repository import (
    PurchaseInvoiceLineRepository,
    PurchaseInvoiceRepository,
    SupplierRepository,
)
from app.modules.purchases.schemas import (
    PurchaseInvoiceCreate,
    PurchaseInvoiceLineCreate,
    PurchaseInvoiceLineUpdate,
    PurchaseInvoiceUpdate,
    SupplierCreate,
    SupplierUpdate,
)

pytestmark = pytest.mark.asyncio

EXPECTED_SUPPLIER_CRUD_FLUSHES = 3
EXPECTED_PURCHASE_CRUD_FLUSHES = 3
EXPECTED_LINE_CRUD_FLUSHES = 3


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


def build_supplier_create_request() -> SupplierCreate:
    """Build a valid supplier create request."""
    return SupplierCreate(
        name="Aarav Wholesale",
        email="billing@example.com",
        phone="+919876543210",
        gstin="29ABCDE1234F1Z5",
        pan="ABCDE1234F",
        address="Bengaluru",
        payment_terms="Net 30",
    )


def build_supplier() -> Supplier:
    """Build a supplier model."""
    return Supplier(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        supplier_code="SUP-0001",
        name="Aarav Wholesale",
        email="billing@example.com",
        gstin="29ABCDE1234F1Z5",
        is_active=True,
    )


def build_purchase_create_request(
    supplier_id: uuid.UUID | None = None,
) -> PurchaseInvoiceCreate:
    """Build a valid purchase invoice create request."""
    return PurchaseInvoiceCreate(
        supplier_id=supplier_id or uuid.uuid4(),
        invoice_number="SUP-INV-0001",
        invoice_date=date(2026, 6, 1),
        due_date=date(2026, 6, 30),
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        notes="Office equipment",
        attachment_count=1,
        lines=[
            PurchaseInvoiceLineCreate(
                description="Office laptops",
                quantity=Decimal("2.00"),
                unit_cost=Decimal("500.00"),
                tax_rate=Decimal("18.00"),
                line_total=Decimal("1180.00"),
            )
        ],
    )


def build_purchase_invoice() -> PurchaseInvoice:
    """Build a purchase invoice model."""
    return PurchaseInvoice(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        supplier_id=uuid.uuid4(),
        purchase_number="PUR-0001",
        invoice_number="SUP-INV-0001",
        invoice_date=date(2026, 6, 1),
        due_date=date(2026, 6, 30),
        status=PurchaseStatus.DRAFT,
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        attachment_count=1,
    )


def build_purchase_line(
    purchase_invoice_id: uuid.UUID | None = None,
) -> PurchaseInvoiceLine:
    """Build a purchase invoice line model."""
    return PurchaseInvoiceLine(
        id=uuid.uuid4(),
        purchase_invoice_id=purchase_invoice_id or uuid.uuid4(),
        description="Office laptops",
        quantity=Decimal("2.00"),
        unit_cost=Decimal("500.00"),
        tax_rate=Decimal("18.00"),
        line_total=Decimal("1180.00"),
    )


async def test_supplier_repository_crud_and_flush_behavior() -> None:
    """Supplier repository creates, updates, and soft-deletes suppliers."""
    session = build_session_mock()
    repository = SupplierRepository(session)
    business_id = uuid.uuid4()
    supplier = await repository.create(
        build_supplier_create_request(),
        business_id=business_id,
        supplier_code="SUP-0001",
    )

    assert isinstance(supplier, Supplier)
    assert supplier.business_id == business_id
    assert supplier.supplier_code == "SUP-0001"
    cast(Any, session.add).assert_called_with(supplier)

    await repository.update(supplier, SupplierUpdate(name="Aarav Trading"))
    assert supplier.name == "Aarav Trading"

    await repository.delete(supplier)
    assert supplier.is_deleted is True
    assert cast(Any, session.flush).await_count == EXPECTED_SUPPLIER_CRUD_FLUSHES
    cast(Any, session.commit).assert_not_awaited()


async def test_supplier_lookup_search_pagination_and_exists() -> None:
    """Supplier repository supports lookup, search, pagination, and exists."""
    session = build_session_mock()
    supplier = build_supplier()
    cast(Any, session.execute).return_value = ExecuteResult(
        one_or_none=supplier,
        one=1,
        items=[supplier],
    )
    repository = SupplierRepository(session)

    assert await repository.get_by_id(supplier.id) is supplier
    assert (
        await repository.get_by_supplier_code(
            business_id=supplier.business_id,
            supplier_code=supplier.supplier_code,
        )
        is supplier
    )
    assert (
        await repository.get_by_gstin(
            business_id=supplier.business_id,
            gstin="29abcde1234f1z5",
        )
        is supplier
    )

    page = await repository.list(
        business_id=supplier.business_id,
        pagination=PaginationParams(page=1, size=10),
        filters=FilterParams(
            filters=[FilterCondition(field="is_active", operator="eq", value=True)],
            sort=[SortCondition(field="name", direction="asc")],
        ),
        sort="name",
    )
    search_page = await repository.search(
        business_id=supplier.business_id,
        query="Aarav",
        pagination=PaginationParams(page=1, size=10),
    )

    assert page.items == [supplier]
    assert search_page.items == [supplier]
    assert page.meta.total == 1
    assert (
        await repository.exists(
            business_id=supplier.business_id,
            supplier_code=supplier.supplier_code,
        )
        is True
    )


async def test_purchase_repository_crud_and_flush_behavior() -> None:
    """Purchase repository creates, updates, and soft-deletes invoices."""
    session = build_session_mock()
    repository = PurchaseInvoiceRepository(session)
    business_id = uuid.uuid4()
    supplier_id = uuid.uuid4()
    purchase_invoice = await repository.create(
        build_purchase_create_request(supplier_id),
        business_id=business_id,
        purchase_number="PUR-0001",
    )

    assert isinstance(purchase_invoice, PurchaseInvoice)
    assert purchase_invoice.business_id == business_id
    assert purchase_invoice.purchase_number == "PUR-0001"
    assert len(purchase_invoice.lines) == 1

    await repository.update(purchase_invoice, PurchaseInvoiceUpdate(notes="Updated"))
    assert purchase_invoice.notes == "Updated"

    await repository.delete(purchase_invoice)
    assert purchase_invoice.is_deleted is True
    assert cast(Any, session.flush).await_count == EXPECTED_PURCHASE_CRUD_FLUSHES
    cast(Any, session.commit).assert_not_awaited()


async def test_purchase_lookup_filtering_sorting_search_and_exists() -> None:
    """Purchase repository supports lookup, filtering, sorting, and search."""
    session = build_session_mock()
    purchase_invoice = build_purchase_invoice()
    cast(Any, session.execute).return_value = ExecuteResult(
        one_or_none=purchase_invoice,
        one=1,
        items=[purchase_invoice],
    )
    repository = PurchaseInvoiceRepository(session)

    assert await repository.get_by_id(purchase_invoice.id) is purchase_invoice
    assert (
        await repository.get_by_purchase_number(
            business_id=purchase_invoice.business_id,
            purchase_number=purchase_invoice.purchase_number,
        )
        is purchase_invoice
    )
    assert (
        await repository.get_by_invoice_number(
            business_id=purchase_invoice.business_id,
            invoice_number=purchase_invoice.invoice_number,
        )
        is purchase_invoice
    )

    page = await repository.list(
        business_id=purchase_invoice.business_id,
        pagination=PaginationParams(page=1, size=10),
        filters=FilterParams(
            filters=[
                FilterCondition(
                    field="status",
                    operator="eq",
                    value=PurchaseStatus.DRAFT.value,
                )
            ],
        ),
        sort="supplier_name",
        supplier_id=purchase_invoice.supplier_id,
        status=PurchaseStatus.DRAFT,
        invoice_date_from=date(2026, 6, 1),
        invoice_date_to=date(2026, 6, 30),
        due_date_from=date(2026, 6, 1),
        due_date_to=date(2026, 7, 1),
        purchase_number=purchase_invoice.purchase_number,
        invoice_number=purchase_invoice.invoice_number,
    )
    search_page = await repository.search(
        business_id=purchase_invoice.business_id,
        query="SUP-INV",
        pagination=PaginationParams(page=1, size=10),
    )

    assert page.items == [purchase_invoice]
    assert search_page.items == [purchase_invoice]
    assert page.meta.total == 1
    assert (
        await repository.exists(
            business_id=purchase_invoice.business_id,
            purchase_number=purchase_invoice.purchase_number,
        )
        is True
    )


async def test_purchase_line_repository_crud_and_flush_behavior() -> None:
    """Purchase line repository creates, updates, lists, and soft-deletes lines."""
    session = build_session_mock()
    purchase_invoice_id = uuid.uuid4()
    line = build_purchase_line(purchase_invoice_id)
    cast(Any, session.execute).return_value = ExecuteResult(
        one_or_none=line,
        items=[line],
    )
    repository = PurchaseInvoiceLineRepository(session)

    created = await repository.create(
        PurchaseInvoiceLineCreate(
            description="Office laptops",
            quantity=Decimal("2.00"),
            unit_cost=Decimal("500.00"),
            tax_rate=Decimal("18.00"),
            line_total=Decimal("1180.00"),
        ),
        purchase_invoice_id=purchase_invoice_id,
    )
    assert isinstance(created, PurchaseInvoiceLine)
    assert created.purchase_invoice_id == purchase_invoice_id

    assert await repository.get_by_id(line.id) is line
    assert await repository.list_by_purchase(purchase_invoice_id) == [line]

    await repository.update(created, PurchaseInvoiceLineUpdate(description="Laptops"))
    assert created.description == "Laptops"

    await repository.delete(created)
    assert created.is_deleted is True
    assert cast(Any, session.flush).await_count == EXPECTED_LINE_CRUD_FLUSHES
    cast(Any, session.commit).assert_not_awaited()


async def test_purchase_repositories_are_registered_in_unit_of_work() -> None:
    """SQLAlchemy Unit of Work exposes purchase repositories."""
    session = build_session_mock()
    unit_of_work = SQLAlchemyUnitOfWork(lambda: session)

    async with unit_of_work as active_uow:
        assert isinstance(active_uow.suppliers, SupplierRepository)
        assert isinstance(active_uow.purchase_invoices, PurchaseInvoiceRepository)
        assert isinstance(
            active_uow.purchase_invoice_lines,
            PurchaseInvoiceLineRepository,
        )
        await active_uow.commit()

    cast(Any, session.commit).assert_awaited_once()
    cast(Any, session.rollback).assert_not_awaited()
    cast(Any, session.close).assert_awaited_once()
