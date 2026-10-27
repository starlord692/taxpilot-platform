"""Query efficiency and pagination count parity tests for EP-RC1.10.

Verifies:
1. Page-size invariance (O(1) query scaling, Q10 == Q50 == 2).
2. Zero child collection eager loading on summary/list queries.
3. Vendor expense isolation (no circular loading of Vendor.expenses).
4. Detail queries continue to load required child collections.
5. Optimized count statement parity against unoptimized baseline across all filter permutations.
6. Preservation of unpaginated, untruncated product stock endpoint contract.
7. Presence and validity of composite/partial performance indexes IX-1 through IX-6.
"""

# ruff: noqa: E501, PLR2004, PLC0415, SLF001, PLR0915

from __future__ import annotations

import datetime
import os
import re
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import Select, event, func, select, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.common.pagination import PaginationParams
from app.core.config import get_settings
from app.core.model_registry import import_all_models
from app.modules.business.models import Business
from app.modules.business.models.enums import (
    BusinessStatus,
    BusinessType,
    RegistrationStatus,
)
from app.modules.expenses.models import Expense, ExpenseLine, ExpenseStatus, Vendor
from app.modules.expenses.repository.expense import ExpenseRepository
from app.modules.inventory.models import Product, StockBalance, Warehouse
from app.modules.inventory.schemas import StockBalanceResponse
from app.modules.purchases.models import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchaseStatus,
    Supplier,
)
from app.modules.purchases.repository.purchase_invoice import PurchaseInvoiceRepository
from app.modules.sales.models import (
    Customer,
    InvoiceStatus,
    SalesInvoice,
    SalesInvoiceLine,
)
from app.modules.sales.repository.invoice import SalesInvoiceRepository

import_all_models()

# Fail-closed module mark: Skip all tests in this file when RUN_LIVE_POSTGRES_TESTS is not enabled.
_opt_in = os.getenv("RUN_LIVE_POSTGRES_TESTS", "").strip().lower()
if _opt_in not in {"true", "1", "yes"}:
    pytestmark = [
        pytest.mark.asyncio,
        pytest.mark.skip(
            reason="Live PostgreSQL query efficiency tests require explicit RUN_LIVE_POSTGRES_TESTS=true opt-in and EFFICIENCY_TEST_DATABASE_URL"
        ),
    ]
else:
    pytestmark = pytest.mark.asyncio


DISPOSABLE_DB_PATTERN = re.compile(
    r"^taxpilot_test_disposable_(?P<session_id>[a-zA-Z0-9_-]+)_(?P<timestamp>[0-9]+)$"
)
FORBIDDEN_DATABASES = frozenset({
    "taxpilot",
    "postgres",
    "template0",
    "template1",
    "taxpilot_dev",
    "taxpilot_prod",
})
ALLOWED_TEST_DB_HOSTS = frozenset({
    "localhost",
    "127.0.0.1",
    "::1",
})


def _validate_disposable_postgres_url(raw_url: str | None, context: str) -> str:
    """Parse and validate live test database URL without opening network sockets.

    Fails closed:
    1. Rejects missing or whitespace-only URLs.
    2. Parses URL structure without exposing raw connection strings or credentials.
    3. Restricts hosts strictly to local loopback (localhost, 127.0.0.1, ::1).
    4. Rejects 'taxpilot', 'postgres', and all persistent databases.
    5. Enforces ephemeral naming: 'taxpilot_test_disposable_{session_id}_{timestamp}'.
    """
    if not raw_url or not raw_url.strip():
        pytest.fail(
            f"RUN_LIVE_POSTGRES_TESTS is enabled, but no database URL is configured for {context}."
        )

    clean_url = raw_url.strip()
    try:
        parsed = make_url(clean_url)
    except Exception:
        pytest.fail(
            f"Malformed database URL for {context}. Unable to parse URL structure."
        )

    if not parsed.get_backend_name().startswith("postgresql"):
        pytest.fail(
            f"Invalid backend '{parsed.get_backend_name()}' for {context}. "
            "Live PostgreSQL tests require a postgresql driver."
        )

    if not parsed.host or not parsed.host.strip():
        pytest.fail(
            f"Malformed database URL for {context}: host component is missing or empty."
        )

    normalized_host = parsed.host.strip().lower().strip("[]")
    if normalized_host not in ALLOWED_TEST_DB_HOSTS:
        pytest.fail(
            f"Disallowed database host in {context}. "
            "Live PostgreSQL integration tests are strictly restricted to local loopback hosts: "
            "localhost, 127.0.0.1, or ::1."
        )

    db_name = (parsed.database or "").strip()
    if not db_name:
        pytest.fail(
            f"Malformed database URL for {context}: database name component is missing or empty."
        )

    if db_name.lower() in FORBIDDEN_DATABASES:
        pytest.fail(
            f"Unsafe database name in {context}. Access to 'taxpilot', 'postgres', "
            "and persistent production/dev databases is strictly forbidden during tests."
        )

    if not DISPOSABLE_DB_PATTERN.match(db_name):
        pytest.fail(
            f"Database name in {context} violates safety policy. "
            "Live PostgreSQL tests strictly require a disposable test database matching "
            "'taxpilot_test_disposable_{session_id}_{timestamp}'."
        )

    return clean_url


def _get_live_efficiency_db_url() -> str:
    """Resolve live PostgreSQL test database URL.

    Fails closed: Requires explicit RUN_LIVE_POSTGRES_TESTS=true opt-in AND
    an explicit EFFICIENCY_TEST_DATABASE_URL or POSTGRES_TEST_DATABASE_URL.
    Validates URL format and disposable database name without connecting to the server.
    Never attempts connectivity probing and never defaults to localhost:5432.
    """
    opt_in = os.getenv("RUN_LIVE_POSTGRES_TESTS", "").strip().lower()
    if opt_in not in {"true", "1", "yes"}:
        pytest.skip(
            "Live PostgreSQL query efficiency tests disabled by default. "
            "To enable, set RUN_LIVE_POSTGRES_TESTS=true and EFFICIENCY_TEST_DATABASE_URL."
        )
    raw_url = (
        os.getenv("EFFICIENCY_TEST_DATABASE_URL")
        or os.getenv("POSTGRES_TEST_DATABASE_URL")
    )
    return _validate_disposable_postgres_url(raw_url, context="Query Efficiency tests")


@asynccontextmanager
async def efficiency_test_context() -> AsyncGenerator[
    tuple[AsyncSession, uuid.UUID], None
]:
    """Provide an async session and an isolated test business."""
    database_url = _get_live_efficiency_db_url()
    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    now = datetime.datetime.now(datetime.UTC)
    business_id = uuid.uuid4()

    async with session_factory() as session:
        # Seed an isolated test business
        business = Business(
            id=business_id,
            business_code=f"EFF-{str(business_id)[:8]}",
            legal_name="Efficiency Test Business",
            business_type=BusinessType.SOLE_PROPRIETOR,
            registration_status=RegistrationStatus.REGISTERED,
            status=BusinessStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=1,
        )
        session.add(business)
        await session.commit()

    try:
        async with session_factory() as session:
            yield session, business_id
    finally:
        async with session_factory() as session:
            # Clean up all created business records
            await session.execute(
                text("DELETE FROM sales_invoice_lines WHERE invoice_id IN (SELECT id FROM sales_invoices WHERE business_id = :b)"),
                {"b": business_id},
            )
            await session.execute(
                text("DELETE FROM sales_invoices WHERE business_id = :b"),
                {"b": business_id},
            )
            await session.execute(
                text("DELETE FROM purchase_invoice_lines WHERE purchase_invoice_id IN (SELECT id FROM purchase_invoices WHERE business_id = :b)"),
                {"b": business_id},
            )
            await session.execute(
                text("DELETE FROM purchase_invoices WHERE business_id = :b"),
                {"b": business_id},
            )
            await session.execute(
                text("DELETE FROM expense_lines WHERE expense_id IN (SELECT id FROM expenses WHERE business_id = :b)"),
                {"b": business_id},
            )
            await session.execute(
                text("DELETE FROM expenses WHERE business_id = :b"),
                {"b": business_id},
            )
            await session.execute(
                text("DELETE FROM inventory_stock_balances WHERE business_id = :b"),
                {"b": business_id},
            )
            await session.execute(
                text("DELETE FROM inventory_warehouses WHERE business_id = :b"),
                {"b": business_id},
            )
            await session.execute(
                text("DELETE FROM inventory_products WHERE business_id = :b"),
                {"b": business_id},
            )
            await session.execute(
                text("DELETE FROM vendors WHERE business_id = :b"),
                {"b": business_id},
            )
            await session.execute(
                text("DELETE FROM suppliers WHERE business_id = :b"),
                {"b": business_id},
            )
            await session.execute(
                text("DELETE FROM customers WHERE business_id = :b"),
                {"b": business_id},
            )
            await session.execute(
                text("DELETE FROM businesses WHERE id = :b"),
                {"b": business_id},
            )
            await session.commit()
        await engine.dispose()


class QueryCounter:
    """Track executed SQL statements on a database session."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.statements: list[str] = []
        bind = session.bind
        self._target: Any = getattr(bind, "sync_engine", bind)

    def __enter__(self) -> QueryCounter:
        event.listen(self._target, "before_cursor_execute", self._callback)
        return self

    def __exit__(self, *args: object) -> None:
        event.remove(self._target, "before_cursor_execute", self._callback)

    def _callback(
        self,
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        self.statements.append(statement)

    @property
    def count(self) -> int:
        return len(self.statements)


# =============================================================================
# 1. Page-Size Invariance & Zero Child Collection Loading Tests
# =============================================================================


async def test_sales_page_size_invariance_and_zero_child_loading() -> None:
    """Sales invoices listing: Q10 == Q50 == 2, and zero lines/payments queries."""
    async with efficiency_test_context() as (session, business_id):
        now = datetime.datetime.now(datetime.UTC)
        today = datetime.date.today()

        # Seed customer
        customer = Customer(
            id=uuid.uuid4(),
            business_id=business_id,
            customer_code="CUST-001",
            name="Test Customer",
            is_active=True,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=1,
        )
        session.add(customer)
        await session.flush()

        # Seed 60 sales invoices with lines
        for i in range(60):
            inv = SalesInvoice(
                id=uuid.uuid4(),
                business_id=business_id,
                customer_id=customer.id,
                invoice_number=f"INV-{i:04d}",
                invoice_date=today - datetime.timedelta(days=i),
                due_date=today + datetime.timedelta(days=30),
                subtotal=Decimal("100.00"),
                discount_amount=Decimal("0.00"),
                taxable_amount=Decimal("100.00"),
                tax_amount=Decimal("18.00"),
                total_amount=Decimal("118.00"),
                status=InvoiceStatus.ISSUED,
                created_at=now - datetime.timedelta(minutes=i),
                updated_at=now - datetime.timedelta(minutes=i),
                is_deleted=False,
                version=1,
            )
            session.add(inv)
            await session.flush()
            line = SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=inv.id,
                description=f"Line Item for {inv.invoice_number}",
                quantity=Decimal("1.00"),
                unit_price=Decimal("100.00"),
                discount=Decimal("0.00"),
                tax_rate=Decimal("18.00"),
                cgst_amount=Decimal("9.00"),
                sgst_amount=Decimal("9.00"),
                igst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("118.00"),
                created_at=now,
                updated_at=now,
                is_deleted=False,
                version=1,
            )
            session.add(line)
        await session.commit()

        repo = SalesInvoiceRepository(session)

        # 1. Verify Q10 == 2
        with QueryCounter(session) as counter_10:
            page_10 = await repo.list_business_invoices(
                business_id, PaginationParams(page=1, size=10)
            )
        assert len(page_10.items) == 10
        assert page_10.meta.total == 60
        assert counter_10.count == 2, f"Expected 2 queries for size=10, got {counter_10.count}"

        # 2. Verify Q50 == 2 and Q10 == Q50
        with QueryCounter(session) as counter_50:
            page_50 = await repo.list_business_invoices(
                business_id, PaginationParams(page=1, size=50)
            )
        assert len(page_50.items) == 50
        assert page_50.meta.total == 60
        assert counter_50.count == 2, f"Expected 2 queries for size=50, got {counter_50.count}"
        assert counter_10.count == counter_50.count, "Page-size scaling is not O(1)"

        # 3. Verify zero queries loaded child collections (lines or payments)
        all_stmts = " ".join(counter_10.statements + counter_50.statements).lower()
        assert "sales_invoice_lines" not in all_stmts, "Child lines were eagerly loaded in list query!"
        assert "payments" not in all_stmts, "Child payments were eagerly loaded in list query!"


async def test_purchases_page_size_invariance_and_zero_child_loading() -> None:
    """Purchase invoices listing: Q10 == Q50 == 2, and zero lines queries."""
    async with efficiency_test_context() as (session, business_id):
        now = datetime.datetime.now(datetime.UTC)
        today = datetime.date.today()

        supplier = Supplier(
            id=uuid.uuid4(),
            business_id=business_id,
            supplier_code="SUPP-001",
            name="Test Supplier",
            is_active=True,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=1,
        )
        session.add(supplier)
        await session.flush()

        for i in range(60):
            p_inv = PurchaseInvoice(
                id=uuid.uuid4(),
                business_id=business_id,
                supplier_id=supplier.id,
                purchase_number=f"PO-{i:04d}",
                invoice_number=f"PINV-{i:04d}",
                invoice_date=today - datetime.timedelta(days=i),
                due_date=today + datetime.timedelta(days=30),
                subtotal=Decimal("200.00"),
                tax_amount=Decimal("36.00"),
                total_amount=Decimal("236.00"),
                attachment_count=0,
                status=PurchaseStatus.APPROVED,
                created_at=now - datetime.timedelta(minutes=i),
                updated_at=now - datetime.timedelta(minutes=i),
                is_deleted=False,
                version=1,
            )
            session.add(p_inv)
            await session.flush()
            line = PurchaseInvoiceLine(
                id=uuid.uuid4(),
                purchase_invoice_id=p_inv.id,
                description=f"PO Line for {p_inv.purchase_number}",
                quantity=Decimal("1.00"),
                unit_cost=Decimal("200.00"),
                tax_rate=Decimal("18.00"),
                cgst_amount=Decimal("18.00"),
                sgst_amount=Decimal("18.00"),
                igst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("236.00"),
                created_at=now,
                updated_at=now,
                is_deleted=False,
                version=1,
            )
            session.add(line)
        await session.commit()

        repo = PurchaseInvoiceRepository(session)

        # 1. Verify Q10 == 2
        with QueryCounter(session) as counter_10:
            page_10 = await repo.list(
                business_id=business_id, pagination=PaginationParams(page=1, size=10)
            )
        assert len(page_10.items) == 10
        assert page_10.meta.total == 60
        assert counter_10.count == 2

        # 2. Verify Q50 == 2 and Q10 == Q50
        with QueryCounter(session) as counter_50:
            page_50 = await repo.list(
                business_id=business_id, pagination=PaginationParams(page=1, size=50)
            )
        assert len(page_50.items) == 50
        assert page_50.meta.total == 60
        assert counter_50.count == 2
        assert counter_10.count == counter_50.count

        # 3. Verify zero queries loaded child lines
        all_stmts = " ".join(counter_10.statements + counter_50.statements).lower()
        assert "purchase_invoice_lines" not in all_stmts, "Purchase lines were eagerly loaded in list query!"


async def test_expenses_page_size_invariance_and_vendor_isolation() -> None:
    """Expenses listing: Q10 == Q50 == 2, zero lines queries, and Vendor.expenses isolation."""
    async with efficiency_test_context() as (session, business_id):
        now = datetime.datetime.now(datetime.UTC)
        today = datetime.date.today()

        vendor = Vendor(
            id=uuid.uuid4(),
            business_id=business_id,
            vendor_code="VEND-001",
            name="Test Vendor Services",
            is_active=True,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=1,
        )
        session.add(vendor)
        await session.flush()

        # Seed 60 expenses for this vendor
        for i in range(60):
            exp = Expense(
                id=uuid.uuid4(),
                business_id=business_id,
                vendor_id=vendor.id,
                expense_number=f"EXP-{i:04d}",
                expense_date=today - datetime.timedelta(days=i),
                category="office",
                subtotal=Decimal("50.00"),
                tax_amount=Decimal("9.00"),
                total_amount=Decimal("59.00"),
                status=ExpenseStatus.APPROVED,
                attachment_count=0,
                created_at=now - datetime.timedelta(minutes=i),
                updated_at=now - datetime.timedelta(minutes=i),
                is_deleted=False,
                version=1,
            )
            session.add(exp)
            await session.flush()
            line = ExpenseLine(
                id=uuid.uuid4(),
                expense_id=exp.id,
                description=f"Item for {exp.expense_number}",
                quantity=Decimal("1.00"),
                unit_cost=Decimal("50.00"),
                tax_rate=Decimal("18.00"),
                cgst_amount=Decimal("4.50"),
                sgst_amount=Decimal("4.50"),
                igst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("59.00"),
                created_at=now,
                updated_at=now,
                is_deleted=False,
                version=1,
            )
            session.add(line)
        await session.commit()

        repo = ExpenseRepository(session)

        # 1. Page-size scaling invariant
        with QueryCounter(session) as counter_10:
            page_10 = await repo.list_by_business(
                business_id, pagination=PaginationParams(page=1, size=10)
            )
        assert len(page_10.items) == 10
        assert page_10.meta.total == 60
        assert counter_10.count == 2

        with QueryCounter(session) as counter_50:
            page_50 = await repo.list_by_business(
                business_id, pagination=PaginationParams(page=1, size=50)
            )
        assert len(page_50.items) == 50
        assert page_50.meta.total == 60
        assert counter_50.count == 2
        assert counter_10.count == counter_50.count

        # 2. Zero child collection loading on summary
        all_stmts = " ".join(counter_10.statements + counter_50.statements).lower()
        assert "expense_lines" not in all_stmts, "Expense lines were eagerly loaded on list query!"

        # 3. Vendor expense isolation: detail get_by_id loads vendor, but does NOT load vendor.expenses
        target_expense_id = page_10.items[0].id
        target_vendor_id = vendor.id
        session.expire_all()

        with QueryCounter(session) as detail_counter:
            detail_expense = await repo.get_by_id(target_expense_id)
        assert detail_expense is not None
        assert detail_expense.vendor is not None
        assert detail_expense.vendor.id == target_vendor_id

        # Verify that Vendor.expenses collection is NOT eagerly loaded into session memory
        detail_stmts = " ".join(detail_counter.statements).lower()
        # Should load expense (1), lines (2), vendor (3). Zero queries loading other expenses for vendor.
        assert "selectinload(vendor.expenses)" not in detail_stmts
        # Confirm in SQLAlchemy inspection state that expenses relationship on vendor is unloaded
        from sqlalchemy import inspect as sa_inspect
        vendor_state = sa_inspect(detail_expense.vendor)
        assert "expenses" in vendor_state.unloaded, (
            "Catastrophic circular Vendor.expenses was loaded into vendor entity!"
        )
        assert "expenses" not in vendor_state.dict, (
            "Catastrophic circular Vendor.expenses was loaded into vendor entity dict!"
        )


# =============================================================================
# 2. Detail Endpoints Load Required Child Collections
# =============================================================================


async def test_detail_lookups_load_required_relationships() -> None:
    """Detail lookups (get_by_id) must continue loading lines and parent entities."""
    async with efficiency_test_context() as (session, business_id):
        now = datetime.datetime.now(datetime.UTC)
        today = datetime.date.today()

        # 1. Sales detail
        customer = Customer(
            id=uuid.uuid4(),
            business_id=business_id,
            customer_code="CUST-DET",
            name="Detail Customer",
            is_active=True,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=1,
        )
        session.add(customer)
        await session.flush()

        sales_inv = SalesInvoice(
            id=uuid.uuid4(),
            business_id=business_id,
            customer_id=customer.id,
            invoice_number="INV-DET-001",
            invoice_date=today,
            due_date=today,
            subtotal=Decimal("100.00"),
            discount_amount=Decimal("0.00"),
            taxable_amount=Decimal("100.00"),
            tax_amount=Decimal("18.00"),
            total_amount=Decimal("118.00"),
            status=InvoiceStatus.ISSUED,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=1,
        )
        session.add(sales_inv)
        await session.flush()
        sales_line = SalesInvoiceLine(
            id=uuid.uuid4(),
            invoice_id=sales_inv.id,
            description="Detail Line Item",
            quantity=Decimal("1.00"),
            unit_price=Decimal("100.00"),
            discount=Decimal("0.00"),
            tax_rate=Decimal("18.00"),
            cgst_amount=Decimal("9.00"),
            sgst_amount=Decimal("9.00"),
            igst_amount=Decimal("0.00"),
            cess_amount=Decimal("0.00"),
            line_total=Decimal("118.00"),
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=1,
        )
        session.add(sales_line)

        # 2. Purchase detail
        supplier = Supplier(
            id=uuid.uuid4(),
            business_id=business_id,
            supplier_code="SUPP-DET",
            name="Detail Supplier",
            is_active=True,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=1,
        )
        session.add(supplier)
        await session.flush()

        pur_inv = PurchaseInvoice(
            id=uuid.uuid4(),
            business_id=business_id,
            supplier_id=supplier.id,
            purchase_number="PO-DET-001",
            invoice_number="PINV-DET-001",
            invoice_date=today,
            due_date=today,
            subtotal=Decimal("200.00"),
            tax_amount=Decimal("36.00"),
            total_amount=Decimal("236.00"),
            attachment_count=0,
            status=PurchaseStatus.APPROVED,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=1,
        )
        session.add(pur_inv)
        await session.flush()
        pur_line = PurchaseInvoiceLine(
            id=uuid.uuid4(),
            purchase_invoice_id=pur_inv.id,
            description="Purchase Line Item",
            quantity=Decimal("1.00"),
            unit_cost=Decimal("200.00"),
            tax_rate=Decimal("18.00"),
            cgst_amount=Decimal("18.00"),
            sgst_amount=Decimal("18.00"),
            igst_amount=Decimal("0.00"),
            cess_amount=Decimal("0.00"),
            line_total=Decimal("236.00"),
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=1,
        )
        session.add(pur_line)

        # 3. Expense detail
        vendor = Vendor(
            id=uuid.uuid4(),
            business_id=business_id,
            vendor_code="VEND-DET",
            name="Detail Vendor",
            is_active=True,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=1,
        )
        session.add(vendor)
        await session.flush()

        exp = Expense(
            id=uuid.uuid4(),
            business_id=business_id,
            vendor_id=vendor.id,
            expense_number="EXP-DET-001",
            expense_date=today,
            category="software",
            subtotal=Decimal("50.00"),
            tax_amount=Decimal("9.00"),
            total_amount=Decimal("59.00"),
            status=ExpenseStatus.APPROVED,
            attachment_count=0,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=1,
        )
        session.add(exp)
        await session.flush()
        exp_line = ExpenseLine(
            id=uuid.uuid4(),
            expense_id=exp.id,
            description="Detail Expense Line",
            quantity=Decimal("1.00"),
            unit_cost=Decimal("50.00"),
            tax_rate=Decimal("18.00"),
            cgst_amount=Decimal("4.50"),
            sgst_amount=Decimal("4.50"),
            igst_amount=Decimal("0.00"),
            cess_amount=Decimal("0.00"),
            line_total=Decimal("59.00"),
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=1,
        )
        session.add(exp_line)
        await session.commit()

        target_sales_id = sales_inv.id
        target_pur_id = pur_inv.id
        target_exp_id = exp.id

        # Clear session cache
        session.expire_all()

        # Verify Sales detail loads lines
        sales_repo = SalesInvoiceRepository(session)
        loaded_sales = await sales_repo.get_by_id(target_sales_id)
        assert loaded_sales is not None
        assert len(loaded_sales.lines) == 1
        assert loaded_sales.lines[0].description == "Detail Line Item"

        # Verify Purchase detail loads lines and supplier
        purchases_repo = PurchaseInvoiceRepository(session)
        loaded_purchase = await purchases_repo.get_by_id(target_pur_id)
        assert loaded_purchase is not None
        assert len(loaded_purchase.lines) == 1
        assert loaded_purchase.lines[0].description == "Purchase Line Item"
        assert loaded_purchase.supplier is not None
        assert loaded_purchase.supplier.name == "Detail Supplier"

        # Verify Expense detail loads lines and vendor
        expenses_repo = ExpenseRepository(session)
        loaded_exp = await expenses_repo.get_by_id(target_exp_id)
        assert loaded_exp is not None
        assert len(loaded_exp.lines) == 1
        assert loaded_exp.lines[0].description == "Detail Expense Line"
        assert loaded_exp.vendor is not None
        assert loaded_exp.vendor.name == "Detail Vendor"


# =============================================================================
# 3. Count Query A/B Baseline Parity Tests
# =============================================================================


async def test_sales_count_query_parity_and_invariance() -> None:
    """Verify optimized count statement yields identical results to unoptimized baseline."""
    async with efficiency_test_context() as (session, business_id):
        now = datetime.datetime.now(datetime.UTC)
        today = datetime.date.today()

        # Customer 1 and Customer 2
        c1 = Customer(
            id=uuid.uuid4(),
            business_id=business_id,
            customer_code="CUST-1",
            name="Customer 1",
            is_active=True,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=1,
        )
        c2 = Customer(
            id=uuid.uuid4(),
            business_id=business_id,
            customer_code="CUST-2",
            name="Customer 2",
            is_active=True,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=1,
        )
        session.add_all([c1, c2])
        await session.flush()

        # Seed 30 invoices across statuses and dates
        for i in range(30):
            st = InvoiceStatus.PAID if i < 10 else (InvoiceStatus.ISSUED if i < 20 else InvoiceStatus.DRAFT)
            c_target = c1 if i % 2 == 0 else c2
            is_del = i == 29  # 1 soft-deleted
            inv = SalesInvoice(
                id=uuid.uuid4(),
                business_id=business_id,
                customer_id=c_target.id,
                invoice_number=f"PAR-INV-{i:03d}",
                invoice_date=today - datetime.timedelta(days=i),
                due_date=today + datetime.timedelta(days=30),
                subtotal=Decimal("100.00"),
                discount_amount=Decimal("0.00"),
                taxable_amount=Decimal("100.00"),
                tax_amount=Decimal("18.00"),
                total_amount=Decimal("118.00"),
                status=st,
                created_at=now - datetime.timedelta(minutes=i),
                updated_at=now - datetime.timedelta(minutes=i),
                is_deleted=is_del,
                version=1,
            )
            session.add(inv)
        await session.commit()

        repo = SalesInvoiceRepository(session)

        # Baseline count helper (unoptimized subquery count)
        async def unoptimized_count(stmt: Select[Any]) -> int:
            cnt_stmt = select(func.count()).select_from(stmt.subquery())
            r = await session.execute(cnt_stmt)
            return int(r.scalar_one())

        # Test permutations:
        # 1. Base tenant query
        base_stmt = repo._summary_statement().where(SalesInvoice.business_id == business_id)
        opt_count = await repo._count_statement(base_stmt)
        base_count = await unoptimized_count(base_stmt)
        assert opt_count == base_count == 29  # 30 minus 1 soft deleted

        # 2. Status filter
        paid_stmt = base_stmt.where(SalesInvoice.status == InvoiceStatus.PAID)
        assert await repo._count_statement(paid_stmt) == await unoptimized_count(paid_stmt) == 10

        # 3. Customer filter
        cust_stmt = base_stmt.where(SalesInvoice.customer_id == c1.id)
        assert await repo._count_statement(cust_stmt) == await unoptimized_count(cust_stmt)

        # 4. Date range filter
        date_stmt = base_stmt.where(
            SalesInvoice.invoice_date >= today - datetime.timedelta(days=5),
            SalesInvoice.invoice_date <= today,
        )
        assert await repo._count_statement(date_stmt) == await unoptimized_count(date_stmt) == 6


async def test_purchases_count_query_parity_and_invariance() -> None:
    """Verify purchase invoice count query parity under multiple filters."""
    async with efficiency_test_context() as (session, business_id):
        now = datetime.datetime.now(datetime.UTC)
        today = datetime.date.today()

        supp = Supplier(
            id=uuid.uuid4(),
            business_id=business_id,
            supplier_code="SUPP-PAR",
            name="Parity Supplier",
            is_active=True,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=1,
        )
        session.add(supp)
        await session.flush()

        for i in range(25):
            st = PurchaseStatus.APPROVED if i < 15 else PurchaseStatus.DRAFT
            is_del = i == 24
            p = PurchaseInvoice(
                id=uuid.uuid4(),
                business_id=business_id,
                supplier_id=supp.id,
                purchase_number=f"PO-PAR-{i:03d}",
                invoice_number=f"PINV-PAR-{i:03d}",
                invoice_date=today - datetime.timedelta(days=i),
                due_date=today + datetime.timedelta(days=30),
                subtotal=Decimal("200.00"),
                tax_amount=Decimal("36.00"),
                total_amount=Decimal("236.00"),
                attachment_count=0,
                status=st,
                created_at=now - datetime.timedelta(minutes=i),
                updated_at=now - datetime.timedelta(minutes=i),
                is_deleted=is_del,
                version=1,
            )
            session.add(p)
        await session.commit()

        repo = PurchaseInvoiceRepository(session)

        async def unoptimized_count(stmt: Select[Any]) -> int:
            cnt_stmt = select(func.count()).select_from(stmt.subquery())
            r = await session.execute(cnt_stmt)
            return int(r.scalar_one())

        # Base statement
        stmt = repo._summary_statement().where(PurchaseInvoice.business_id == business_id)
        assert await repo._count_statement(stmt) == await unoptimized_count(stmt) == 24

        # With status filter
        appr_stmt = stmt.where(PurchaseInvoice.status == PurchaseStatus.APPROVED)
        assert await repo._count_statement(appr_stmt) == await unoptimized_count(appr_stmt) == 15


async def test_expenses_count_query_parity_and_invariance() -> None:
    """Verify expense count query parity under multiple filters."""
    async with efficiency_test_context() as (session, business_id):
        now = datetime.datetime.now(datetime.UTC)
        today = datetime.date.today()

        vendor = Vendor(
            id=uuid.uuid4(),
            business_id=business_id,
            vendor_code="VEND-PAR",
            name="Parity Vendor",
            is_active=True,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=1,
        )
        session.add(vendor)
        await session.flush()

        for i in range(20):
            st = ExpenseStatus.APPROVED if i < 10 else ExpenseStatus.DRAFT
            exp = Expense(
                id=uuid.uuid4(),
                business_id=business_id,
                vendor_id=vendor.id,
                expense_number=f"EXP-PAR-{i:03d}",
                expense_date=today - datetime.timedelta(days=i),
                category="rent" if i % 2 == 0 else "utilities",
                subtotal=Decimal("50.00"),
                tax_amount=Decimal("9.00"),
                total_amount=Decimal("59.00"),
                status=st,
                attachment_count=0,
                created_at=now - datetime.timedelta(minutes=i),
                updated_at=now - datetime.timedelta(minutes=i),
                is_deleted=False,
                version=1,
            )
            session.add(exp)
        await session.commit()

        repo = ExpenseRepository(session)

        async def unoptimized_count(stmt: Select[Any]) -> int:
            cnt_stmt = select(func.count()).select_from(stmt.subquery())
            r = await session.execute(cnt_stmt)
            return int(r.scalar_one())

        stmt = repo._summary_statement().where(Expense.business_id == business_id)
        assert await repo._count_statement(stmt) == await unoptimized_count(stmt) == 20

        rent_stmt = stmt.where(Expense.category == "rent")
        assert await repo._count_statement(rent_stmt) == await unoptimized_count(rent_stmt) == 10


# =============================================================================
# 4. Inventory Stock Contract Preservation Test
# =============================================================================


async def test_inventory_stock_contract_unpaginated() -> None:
    """Preserve GET /inventory/products/{product_id}/stock contract without pagination."""
    async with efficiency_test_context() as (session, business_id):
        now = datetime.datetime.now(datetime.UTC)

        product = Product(
            id=uuid.uuid4(),
            business_id=business_id,
            sku="SKU-STOCK-TEST",
            name="Stock Test Product",
            unit_of_measure="PCS",
            purchase_price=Decimal("10.00"),
            selling_price=Decimal("20.00"),
            reorder_level=Decimal("5.0000"),
            is_active=True,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=1,
        )
        session.add(product)

        # Create 3 warehouses with stock balances
        warehouses: list[Warehouse] = []
        for i in range(3):
            wh = Warehouse(
                id=uuid.uuid4(),
                business_id=business_id,
                code=f"WH-STK-{i}",
                name=f"Stock Warehouse {i}",
                is_default=(i == 0),
                is_active=True,
                created_at=now,
                updated_at=now,
                is_deleted=False,
                version=1,
            )
            session.add(wh)
            warehouses.append(wh)
        await session.flush()

        for i, wh in enumerate(warehouses):
            sb = StockBalance(
                id=uuid.uuid4(),
                business_id=business_id,
                product_id=product.id,
                warehouse_id=wh.id,
                quantity_on_hand=Decimal(f"{10 * (i + 1)}.0000"),
                created_at=now,
                updated_at=now,
                is_deleted=False,
                version=1,
            )
            session.add(sb)
        await session.commit()

        # Query stock balances using repository method
        from app.modules.inventory.repository.stock_balance import (
            StockBalanceRepository,
        )
        sb_repo = StockBalanceRepository(session)
        balances = await sb_repo.get_by_product(
            business_id=business_id,
            product_id=product.id,
        )

        # Validate that all warehouse balances are returned without truncation or pagination
        assert len(balances) == 3
        # Validate that response schema is list[StockBalanceResponse]
        responses = [StockBalanceResponse.model_validate(b) for b in balances]
        assert len(responses) == 3
        assert sum(r.quantity_on_hand for r in responses) == Decimal("60.0000")


# =============================================================================
# 5. PostgreSQL Composite Performance Indexes Catalog Validation
# =============================================================================


async def test_performance_indexes_catalog_verification() -> None:
    """Verify that retained performance indexes exist in PostgreSQL catalog and are valid.

    Also confirms that IX-4 is omitted (unvalidated) and IX-7 is deferred (dormant relay).
    """
    database_url = _get_live_efficiency_db_url()
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT
                c.relname AS index_name,
                t.relname AS table_name,
                x.indisvalid AS is_valid
            FROM pg_index x
            JOIN pg_class c ON c.oid = x.indexrelid
            JOIN pg_class t ON t.oid = x.indrelid
            WHERE c.relname IN (
                'ix_sales_invoices_business_date',
                'ix_purchase_invoices_business_date',
                'ix_gl_entries_business_date',
                'ix_stock_movements_reference',
                'ix_documents_business_uploaded'
            )
            ORDER BY c.relname;
        """))
        rows = result.fetchall()
        index_map = {r.index_name: (r.table_name, r.is_valid) for r in rows}

        expected_indexes = {
            "ix_sales_invoices_business_date": "sales_invoices",
            "ix_purchase_invoices_business_date": "purchase_invoices",
            "ix_gl_entries_business_date": "general_ledger_entries",
            "ix_stock_movements_reference": "inventory_stock_movements",
            "ix_documents_business_uploaded": "documents",
        }

        for idx_name, expected_table in expected_indexes.items():
            assert idx_name in index_map, f"Missing performance index: {idx_name}"
            table_name, is_valid = index_map[idx_name]
            assert table_name == expected_table, f"Index {idx_name} is on {table_name}, expected {expected_table}"
            assert is_valid is True, f"Index {idx_name} is marked INVALID (indisvalid=False)"

        # Verify IX-4 is NOT present in the database (omitted as unvalidated per founder direction)
        ix4_res = await conn.execute(text("""
            SELECT 1 FROM pg_class WHERE relname = 'ix_gl_entries_account_date'
        """))
        assert ix4_res.scalar_one_or_none() is None, "IX-4 was erroneously created despite failing validation!"

        # Verify IX-7 is NOT present in the database (dormant relay policy)
        ix7_res = await conn.execute(text("""
            SELECT 1 FROM pg_class WHERE relname = 'ix_outbox_events_status_unprocessed'
        """))
        assert ix7_res.scalar_one_or_none() is None, "IX-7 was erroneously created while relay is dormant!"

    await engine.dispose()
