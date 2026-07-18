"""Tests for Sales repositories."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PaginationParams
from app.modules.sales.models import (
    Customer,
    InvoiceStatus,
    Payment,
    PaymentMethod,
    SalesInvoice,
    SalesInvoiceLine,
)
from app.modules.sales.repository import (
    CustomerRepository,
    PaymentRepository,
    SalesInvoiceRepository,
)
from app.modules.sales.schemas import (
    CustomerCreateRequest,
    CustomerUpdateRequest,
    InvoiceCreateRequest,
    InvoiceLineRequest,
    InvoiceUpdateRequest,
    PaymentCreateRequest,
)

pytestmark = pytest.mark.asyncio

EXPECTED_DOUBLE_FLUSHES = 2
EXPECTED_CUSTOMER_CRUD_FLUSHES = 4
EXPECTED_LINE_STATUS_FLUSHES = 3


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
    session.delete = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return cast(AsyncSession, session)


def build_customer_create_request() -> CustomerCreateRequest:
    """Build a valid customer create request."""
    return CustomerCreateRequest(
        business_id=uuid.uuid4(),
        customer_code="CUST-0001",
        name="Aarav Enterprises",
        email="billing@example.com",
        phone="+919876543210",
        gstin="29ABCDE1234F1Z5",
        pan="ABCDE1234F",
        billing_address="Bengaluru",
        shipping_address="Mysuru",
    )


def build_customer() -> Customer:
    """Build a customer model."""
    return Customer(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        customer_code="CUST-0001",
        name="Aarav Enterprises",
        email="billing@example.com",
        is_active=True,
    )


def build_invoice_create_request() -> InvoiceCreateRequest:
    """Build a valid invoice create request."""
    return InvoiceCreateRequest(
        business_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        invoice_number="INV-0001",
        invoice_date=date(2026, 4, 1),
        due_date=date(2026, 4, 30),
        subtotal=Decimal("1000.00"),
        discount_amount=Decimal("50.00"),
        taxable_amount=Decimal("950.00"),
        tax_amount=Decimal("171.00"),
        total_amount=Decimal("1121.00"),
        lines=[
            InvoiceLineRequest(
                description="Monthly bookkeeping",
                quantity=Decimal("2.00"),
                unit_price=Decimal("500.00"),
                discount=Decimal("50.00"),
                tax_rate=Decimal("18.00"),
                line_total=Decimal("1121.00"),
            )
        ],
    )


def build_invoice() -> SalesInvoice:
    """Build a sales invoice model."""
    return SalesInvoice(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        invoice_number="INV-0001",
        invoice_date=date(2026, 4, 1),
        status=InvoiceStatus.DRAFT,
        total_amount=Decimal("1121.00"),
    )


def build_payment_create_request(
    invoice_id: uuid.UUID | None = None,
) -> PaymentCreateRequest:
    """Build a valid payment create request."""
    return PaymentCreateRequest(
        invoice_id=invoice_id or uuid.uuid4(),
        payment_date=date(2026, 4, 10),
        amount=Decimal("500.00"),
        payment_method=PaymentMethod.UPI,
        reference_number="UPI-123",
    )


async def test_customer_crud() -> None:
    """Customer repository creates, updates, archives, and restores customers."""
    session = build_session_mock()
    repository = CustomerRepository(session)
    customer = await repository.create(build_customer_create_request())

    assert isinstance(customer, Customer)
    assert customer.customer_code == "CUST-0001"
    cast(Any, session.add).assert_called_once_with(customer)

    result = await repository.update(
        customer,
        CustomerUpdateRequest(name="Aarav Trading", is_active=True),
    )
    assert result is customer
    assert customer.name == "Aarav Trading"

    await repository.archive(customer)
    assert customer.is_active is False

    await repository.restore(customer)
    assert customer.is_active is True
    assert cast(Any, session.flush).await_count == EXPECTED_CUSTOMER_CRUD_FLUSHES


async def test_customer_lookup_and_exists() -> None:
    """Customer repository lookup methods return matching records."""
    session = build_session_mock()
    customer = build_customer()
    cast(Any, session.execute).return_value = ExecuteResult(one_or_none=customer)
    repository = CustomerRepository(session)

    assert await repository.get_by_id(customer.id) is customer
    assert (
        await repository.get_by_customer_code(
            business_id=customer.business_id,
            customer_code=customer.customer_code,
        )
        is customer
    )
    assert (
        await repository.get_by_email(
            business_id=customer.business_id,
            email="BILLING@EXAMPLE.COM",
        )
        is customer
    )
    assert (
        await repository.exists_by_code(
            business_id=customer.business_id,
            customer_code=customer.customer_code,
        )
        is True
    )
    assert (
        await repository.exists_by_email(
            business_id=customer.business_id,
            email="billing@example.com",
        )
        is True
    )


async def test_customer_business_isolation_and_pagination() -> None:
    """Customer list is scoped by business and paginated."""
    session = build_session_mock()
    customer = build_customer()
    cast(Any, session.execute).return_value = ExecuteResult(items=[customer], one=1)
    repository = CustomerRepository(session)

    page = await repository.list_business_customers(
        customer.business_id,
        PaginationParams(page=1, size=10),
    )

    assert page.items == [customer]
    assert page.meta.total == 1
    assert page.meta.page == 1


async def test_invoice_crud_and_lookup() -> None:
    """Invoice repository creates, updates, and looks up invoices."""
    session = build_session_mock()
    repository = SalesInvoiceRepository(session)
    request = build_invoice_create_request()
    invoice = await repository.create(request)

    assert isinstance(invoice, SalesInvoice)
    assert invoice.invoice_number == "INV-0001"
    assert len(invoice.lines) == 1
    cast(Any, session.flush).assert_awaited_once()

    await repository.update(invoice, InvoiceUpdateRequest(notes="Updated"))
    assert invoice.notes == "Updated"

    cast(Any, session.execute).return_value = ExecuteResult(one_or_none=invoice)
    assert await repository.get_by_id(invoice.id) is invoice
    assert (
        await repository.get_by_invoice_number(
            business_id=invoice.business_id,
            invoice_number=invoice.invoice_number,
        )
        is invoice
    )


async def test_invoice_lists_support_business_customer_and_pagination() -> None:
    """Invoice repository lists by business and customer."""
    session = build_session_mock()
    invoice = build_invoice()
    cast(Any, session.execute).return_value = ExecuteResult(items=[invoice], one=1)
    repository = SalesInvoiceRepository(session)

    business_page = await repository.list_business_invoices(
        invoice.business_id,
        PaginationParams(page=1, size=10),
    )
    customer_page = await repository.list_customer_invoices(
        invoice.customer_id,
        PaginationParams(page=1, size=10),
    )

    assert business_page.items == [invoice]
    assert customer_page.items == [invoice]
    assert business_page.meta.total == 1
    assert customer_page.meta.total == 1


async def test_invoice_line_and_status_updates() -> None:
    """Invoice repository adds/removes lines and marks status."""
    session = build_session_mock()
    repository = SalesInvoiceRepository(session)
    invoice = build_invoice()

    line = await repository.add_line(
        invoice,
        InvoiceLineRequest(
            description="Consulting",
            quantity=Decimal("1.00"),
            unit_price=Decimal("250.00"),
            line_total=Decimal("250.00"),
        ),
    )
    assert isinstance(line, SalesInvoiceLine)
    assert line.invoice_id == invoice.id

    await repository.mark_status(invoice, InvoiceStatus.ISSUED)
    assert invoice.status == InvoiceStatus.ISSUED

    await repository.remove_line(line)
    assert line.is_deleted is True
    assert cast(Any, session.flush).await_count == EXPECTED_LINE_STATUS_FLUSHES


async def test_payment_crud_list_and_total_paid() -> None:
    """Payment repository creates payments, lists them, and totals paid amount."""
    session = build_session_mock()
    invoice_id = uuid.uuid4()
    payment = Payment(
        id=uuid.uuid4(),
        invoice_id=invoice_id,
        payment_date=date(2026, 4, 10),
        amount=Decimal("500.00"),
        payment_method=PaymentMethod.UPI,
    )
    cast(Any, session.execute).side_effect = [
        ExecuteResult(items=[payment]),
        ExecuteResult(one=Decimal("500.00")),
    ]
    repository = PaymentRepository(session)

    created = await repository.create(build_payment_create_request(invoice_id))
    assert isinstance(created, Payment)
    assert created.amount == Decimal("500.00")

    payments = await repository.list_invoice_payments(invoice_id)
    total_paid = await repository.total_paid(invoice_id)

    assert payments == [payment]
    assert total_paid == Decimal("500.00")
    cast(Any, session.flush).assert_awaited_once()
