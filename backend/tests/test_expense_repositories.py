"""Tests for Expense Management repositories."""

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
from app.modules.expenses.models import (
    Expense,
    ExpenseCategory,
    ExpenseLine,
    ExpenseStatus,
    Vendor,
)
from app.modules.expenses.repository import (
    ExpenseLineRepository,
    ExpenseRepository,
    VendorRepository,
)
from app.modules.expenses.schemas import (
    ExpenseCreate,
    ExpenseLineCreate,
    ExpenseLineUpdate,
    ExpenseUpdate,
    VendorCreate,
    VendorUpdate,
)

pytestmark = pytest.mark.asyncio

EXPECTED_VENDOR_CRUD_FLUSHES = 3
EXPECTED_EXPENSE_CRUD_FLUSHES = 3
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
    return cast(AsyncSession, session)


def build_vendor_create_request() -> VendorCreate:
    """Build a valid vendor create request."""
    return VendorCreate(
        name="Aarav Supplies",
        email="billing@example.com",
        phone="+919876543210",
        gstin="29ABCDE1234F1Z5",
        pan="ABCDE1234F",
        address="Bengaluru",
    )


def build_vendor() -> Vendor:
    """Build a vendor model."""
    return Vendor(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        vendor_code="VEND-0001",
        name="Aarav Supplies",
        email="billing@example.com",
        is_active=True,
    )


def build_expense_create_request(
    vendor_id: uuid.UUID | None = None,
) -> ExpenseCreate:
    """Build a valid expense create request."""
    return ExpenseCreate(
        vendor_id=vendor_id,
        expense_date=date(2026, 5, 1),
        category=ExpenseCategory.SOFTWARE,
        description="Accounting software subscription",
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        notes="Annual subscription",
        attachment_count=1,
        lines=[
            ExpenseLineCreate(
                description="Cloud hosting",
                quantity=Decimal("2.00"),
                unit_cost=Decimal("500.00"),
                tax_rate=Decimal("18.00"),
                line_total=Decimal("1180.00"),
            )
        ],
    )


def build_expense() -> Expense:
    """Build an expense model."""
    return Expense(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        vendor_id=uuid.uuid4(),
        expense_number="EXP-0001",
        expense_date=date(2026, 5, 1),
        category=ExpenseCategory.SOFTWARE,
        status=ExpenseStatus.DRAFT,
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        attachment_count=1,
    )


def build_expense_line(expense_id: uuid.UUID | None = None) -> ExpenseLine:
    """Build an expense line model."""
    return ExpenseLine(
        id=uuid.uuid4(),
        expense_id=expense_id or uuid.uuid4(),
        description="Cloud hosting",
        quantity=Decimal("2.00"),
        unit_cost=Decimal("500.00"),
        tax_rate=Decimal("18.00"),
        line_total=Decimal("1180.00"),
    )


async def test_vendor_repository_crud_and_flush_behavior() -> None:
    """Vendor repository creates, updates, and soft-deletes vendors."""
    session = build_session_mock()
    repository = VendorRepository(session)
    business_id = uuid.uuid4()
    vendor = await repository.create(
        build_vendor_create_request(),
        business_id=business_id,
        vendor_code="VEND-0001",
    )

    assert isinstance(vendor, Vendor)
    assert vendor.business_id == business_id
    assert vendor.vendor_code == "VEND-0001"
    cast(Any, session.add).assert_called_with(vendor)

    await repository.update(vendor, VendorUpdate(name="Aarav Trading"))
    assert vendor.name == "Aarav Trading"

    await repository.delete(vendor)
    assert vendor.is_deleted is True
    assert cast(Any, session.flush).await_count == EXPECTED_VENDOR_CRUD_FLUSHES
    cast(Any, session.commit).assert_not_awaited()


async def test_vendor_lookup_search_business_isolation_and_pagination() -> None:
    """Vendor repository supports lookup, search, pagination, and business scope."""
    session = build_session_mock()
    vendor = build_vendor()
    cast(Any, session.execute).return_value = ExecuteResult(
        one_or_none=vendor,
        one=1,
        items=[vendor],
    )
    repository = VendorRepository(session)

    assert await repository.get_by_id(vendor.id) is vendor
    assert (
        await repository.get_by_vendor_code(
            business_id=vendor.business_id,
            vendor_code=vendor.vendor_code,
        )
        is vendor
    )

    page = await repository.list_by_business(
        vendor.business_id,
        PaginationParams(page=1, size=10),
        filters=FilterParams(
            filters=[FilterCondition(field="is_active", operator="eq", value=True)],
            sort=[SortCondition(field="name", direction="asc")],
        ),
        sort="name",
    )
    search_page = await repository.search(
        business_id=vendor.business_id,
        query="Aarav",
        pagination=PaginationParams(page=1, size=10),
    )

    assert page.items == [vendor]
    assert search_page.items == [vendor]
    assert page.meta.total == 1


async def test_expense_repository_crud_and_flush_behavior() -> None:
    """Expense repository creates, updates, and soft-deletes expenses."""
    session = build_session_mock()
    repository = ExpenseRepository(session)
    business_id = uuid.uuid4()
    vendor_id = uuid.uuid4()
    expense = await repository.create(
        build_expense_create_request(vendor_id),
        business_id=business_id,
        expense_number="EXP-0001",
    )

    assert isinstance(expense, Expense)
    assert expense.business_id == business_id
    assert expense.expense_number == "EXP-0001"
    assert len(expense.lines) == 1

    await repository.update(expense, ExpenseUpdate(notes="Updated"))
    assert expense.notes == "Updated"

    await repository.delete(expense)
    assert expense.is_deleted is True
    assert cast(Any, session.flush).await_count == EXPECTED_EXPENSE_CRUD_FLUSHES
    cast(Any, session.commit).assert_not_awaited()


async def test_expense_lookup_pagination_filtering_and_business_isolation() -> None:
    """Expense repository supports lookup, filtering, and business scope."""
    session = build_session_mock()
    expense = build_expense()
    cast(Any, session.execute).return_value = ExecuteResult(
        one_or_none=expense,
        one=1,
        items=[expense],
    )
    repository = ExpenseRepository(session)

    assert await repository.get_by_id(expense.id) is expense
    assert (
        await repository.get_by_expense_number(
            business_id=expense.business_id,
            expense_number=expense.expense_number,
        )
        is expense
    )

    page = await repository.list_by_business(
        expense.business_id,
        PaginationParams(page=1, size=10),
        filters=FilterParams(
            filters=[
                FilterCondition(
                    field="category",
                    operator="eq",
                    value=ExpenseCategory.SOFTWARE.value,
                )
            ],
        ),
        sort="-expense_date",
        vendor_id=expense.vendor_id,
        status=ExpenseStatus.DRAFT,
        expense_date_from=date(2026, 5, 1),
        expense_date_to=date(2026, 5, 31),
    )
    vendor_page = await repository.list_by_vendor(
        cast(uuid.UUID, expense.vendor_id),
        PaginationParams(page=1, size=10),
    )
    status_page = await repository.list_by_status(
        business_id=expense.business_id,
        status=ExpenseStatus.DRAFT,
        pagination=PaginationParams(page=1, size=10),
    )

    assert page.items == [expense]
    assert vendor_page.items == [expense]
    assert status_page.items == [expense]
    assert page.meta.total == 1


async def test_expense_line_repository_crud_and_flush_behavior() -> None:
    """Expense line repository creates, updates, lists, and soft-deletes lines."""
    session = build_session_mock()
    expense_id = uuid.uuid4()
    line = build_expense_line(expense_id)
    cast(Any, session.execute).return_value = ExecuteResult(
        one_or_none=line,
        items=[line],
    )
    repository = ExpenseLineRepository(session)

    created = await repository.create(
        ExpenseLineCreate(
            description="Cloud hosting",
            quantity=Decimal("2.00"),
            unit_cost=Decimal("500.00"),
            tax_rate=Decimal("18.00"),
            line_total=Decimal("1180.00"),
        ),
        expense_id=expense_id,
    )
    assert isinstance(created, ExpenseLine)
    assert created.expense_id == expense_id

    assert await repository.get_by_id(line.id) is line
    assert await repository.list_by_expense(expense_id) == [line]

    await repository.update(created, ExpenseLineUpdate(description="Hosting"))
    assert created.description == "Hosting"

    await repository.delete(created)
    assert created.is_deleted is True
    assert cast(Any, session.flush).await_count == EXPECTED_LINE_CRUD_FLUSHES
    cast(Any, session.commit).assert_not_awaited()
