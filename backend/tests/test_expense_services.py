"""Tests for Expense Management services."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Self

import pytest

import app.modules.business.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
from app.common.events import Event, EventDispatcher
from app.common.pagination import Page, PaginationParams
from app.modules.expenses.events import (
    ExpenseApprovedEvent,
    ExpenseCancelledEvent,
    ExpenseCreatedEvent,
    ExpensePaidEvent,
    ExpenseUpdatedEvent,
    VendorCreatedEvent,
    VendorDeactivatedEvent,
    VendorUpdatedEvent,
)
from app.modules.expenses.exceptions import (
    ExpenseValidationException,
    InvalidExpenseStatusException,
    VendorInactiveException,
)
from app.modules.expenses.models import (
    Expense,
    ExpenseCategory,
    ExpenseLine,
    ExpenseStatus,
    Vendor,
)
from app.modules.expenses.schemas import (
    ExpenseCreate,
    ExpenseLineCreate,
    ExpenseUpdate,
    VendorCreate,
    VendorUpdate,
)
from app.modules.expenses.services import ExpenseService, VendorService
from app.modules.expenses.services.expense_service import (
    ExpenseLinePersistenceRepository,
    ExpensePersistenceRepository,
    ExpenseVendorRepository,
)
from app.modules.expenses.services.vendor_service import VendorPersistenceRepository

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


class FakeVendorRepository:
    """Fake vendor repository for service tests."""

    def __init__(self, vendor: Vendor | None = None) -> None:
        """Initialize fake repository."""
        self.vendor = vendor
        self.created_vendor: Vendor | None = None

    async def create(
        self,
        request: VendorCreate,
        *,
        business_id: uuid.UUID,
        vendor_code: str,
    ) -> Vendor:
        """Create a fake vendor."""
        self.vendor = Vendor(
            id=uuid.uuid4(),
            business_id=business_id,
            vendor_code=vendor_code,
            **request.model_dump(),
        )
        self.created_vendor = self.vendor
        return self.vendor

    async def get_by_id(self, vendor_id: uuid.UUID) -> Vendor | None:
        """Return configured vendor by id."""
        if self.vendor is None or self.vendor.id != vendor_id:
            return None
        return self.vendor

    async def get_by_vendor_code(
        self,
        *,
        business_id: uuid.UUID,
        vendor_code: str,
    ) -> Vendor | None:
        """Return configured vendor by code."""
        if (
            self.vendor is not None
            and self.vendor.business_id == business_id
            and self.vendor.vendor_code == vendor_code
        ):
            return self.vendor
        return None

    async def list_by_business(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        sort: str | None = None,
    ) -> Page[Vendor]:
        """Return vendor page."""
        _ = sort
        params = pagination or PaginationParams()
        items = (
            [self.vendor]
            if self.vendor is not None and self.vendor.business_id == business_id
            else []
        )
        return Page.create(items=items, total=len(items), params=params)

    async def update(self, vendor: Vendor, request: VendorUpdate) -> Vendor:
        """Update fake vendor."""
        for field_name, value in request.model_dump(exclude_unset=True).items():
            setattr(vendor, field_name, value)
        return vendor

    async def delete(self, vendor: Vendor) -> None:
        """Soft-delete fake vendor."""
        vendor.mark_deleted()


class FakeExpenseRepository:
    """Fake expense repository for service tests."""

    def __init__(
        self,
        expense: Expense | None = None,
        *,
        fail_create: bool = False,
    ) -> None:
        """Initialize fake repository."""
        self.expense = expense
        self.fail_create = fail_create

    async def create(
        self,
        request: ExpenseCreate,
        *,
        business_id: uuid.UUID,
        expense_number: str,
    ) -> Expense:
        """Create a fake expense."""
        if self.fail_create:
            raise RuntimeError("expense create failed")
        expense_id = uuid.uuid4()
        self.expense = Expense(
            id=expense_id,
            business_id=business_id,
            expense_number=expense_number,
            vendor_id=request.vendor_id,
            expense_date=request.expense_date,
            category=request.category,
            description=request.description,
            status=request.status,
            subtotal=request.subtotal,
            tax_amount=request.tax_amount,
            total_amount=request.total_amount,
            notes=request.notes,
            attachment_count=request.attachment_count,
            lines=[
                ExpenseLine(
                    id=uuid.uuid4(),
                    expense_id=expense_id,
                    **line.model_dump(),
                )
                for line in request.lines
            ],
        )
        return self.expense

    async def get_by_id(self, expense_id: uuid.UUID) -> Expense | None:
        """Return configured expense by id."""
        if self.expense is None or self.expense.id != expense_id:
            return None
        return self.expense

    async def get_by_expense_number(
        self,
        *,
        business_id: uuid.UUID,
        expense_number: str,
    ) -> Expense | None:
        """Return configured expense by number."""
        if (
            self.expense is not None
            and self.expense.business_id == business_id
            and self.expense.expense_number == expense_number
        ):
            return self.expense
        return None

    async def list_by_business(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        sort: str | None = None,
        vendor_id: uuid.UUID | None = None,
        status: ExpenseStatus | None = None,
        expense_date_from: date | None = None,
        expense_date_to: date | None = None,
    ) -> Page[Expense]:
        """Return expense page."""
        _ = sort
        _ = vendor_id
        _ = status
        _ = expense_date_from
        _ = expense_date_to
        params = pagination or PaginationParams()
        items = (
            [self.expense]
            if self.expense is not None and self.expense.business_id == business_id
            else []
        )
        return Page.create(items=items, total=len(items), params=params)

    async def update(self, expense: Expense, request: ExpenseUpdate) -> Expense:
        """Update fake expense."""
        update_data = request.model_dump(exclude_unset=True, exclude={"lines"})
        for field_name, value in update_data.items():
            setattr(expense, field_name, value)
        return expense


class FakeExpenseLineRepository:
    """Fake expense line repository for service tests."""

    async def create(
        self,
        request: ExpenseLineCreate,
        *,
        expense_id: uuid.UUID,
    ) -> ExpenseLine:
        """Create a fake expense line."""
        return ExpenseLine(
            id=uuid.uuid4(),
            expense_id=expense_id,
            **request.model_dump(),
        )

    async def delete(self, line: ExpenseLine) -> None:
        """Soft-delete fake expense line."""
        line.mark_deleted()


class FakeExpenseAccountingKernel:
    """Fake accounting kernel for expense service tests."""

    def __init__(self) -> None:
        """Initialize captured accounting calls."""
        self.expense_ids: list[uuid.UUID] = []
        self.payment_expense_ids: list[uuid.UUID] = []

    async def record_expense(self, expense_id: uuid.UUID) -> object:
        """Record approved expense posting calls."""
        self.expense_ids.append(expense_id)
        return object()

    async def record_expense_payment(self, expense_id: uuid.UUID) -> object:
        """Record paid expense posting calls."""
        self.payment_expense_ids.append(expense_id)
        return object()


class FakeExpenseUnitOfWork:
    """Fake Unit of Work for expense service tests."""

    def __init__(
        self,
        *,
        vendor_repository: FakeVendorRepository,
        expense_repository: FakeExpenseRepository | None = None,
    ) -> None:
        """Initialize fake repositories."""
        self.vendors: ExpenseVendorRepository = vendor_repository
        self.expenses: ExpensePersistenceRepository = (
            expense_repository or FakeExpenseRepository()
        )
        self.expense_lines: ExpenseLinePersistenceRepository = (
            FakeExpenseLineRepository()
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


class FakeVendorUnitOfWork:
    """Fake Unit of Work for vendor service tests."""

    def __init__(self, vendor_repository: FakeVendorRepository) -> None:
        """Initialize fake repositories."""
        self.vendors: VendorPersistenceRepository = vendor_repository
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


def build_vendor(*, is_active: bool = True) -> Vendor:
    """Build a vendor model."""
    return Vendor(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        vendor_code="VEND-0001",
        name="Aarav Supplies",
        is_active=is_active,
    )


def build_vendor_request() -> VendorCreate:
    """Build a vendor create request."""
    return VendorCreate(name="Aarav Supplies", is_active=True)


def build_expense(
    *,
    status: ExpenseStatus = ExpenseStatus.DRAFT,
    vendor_id: uuid.UUID | None = None,
    business_id: uuid.UUID | None = None,
) -> Expense:
    """Build an expense model."""
    expense_id = uuid.uuid4()
    return Expense(
        id=expense_id,
        business_id=business_id or uuid.uuid4(),
        vendor_id=vendor_id,
        expense_number="EXP-0001",
        expense_date=date(2026, 5, 1),
        category=ExpenseCategory.SOFTWARE,
        status=status,
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        attachment_count=1,
        lines=[
            ExpenseLine(
                id=uuid.uuid4(),
                expense_id=expense_id,
                description="Cloud hosting",
                quantity=Decimal("2.00"),
                unit_cost=Decimal("500.00"),
                tax_rate=Decimal("18.00"),
                line_total=Decimal("1180.00"),
            )
        ],
    )


def build_expense_request(vendor_id: uuid.UUID | None = None) -> ExpenseCreate:
    """Build an expense create request with advisory totals."""
    return ExpenseCreate(
        vendor_id=vendor_id,
        expense_date=date(2026, 5, 1),
        category=ExpenseCategory.SOFTWARE,
        subtotal=Decimal("1.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("1.00"),
        lines=[
            ExpenseLineCreate(
                description="Cloud hosting",
                quantity=Decimal("2.00"),
                unit_cost=Decimal("500.00"),
                tax_rate=Decimal("18.00"),
                line_total=Decimal("1.00"),
            )
        ],
    )


def build_vendor_service(
    uow: FakeVendorUnitOfWork,
    dispatcher: CapturingEventDispatcher,
) -> VendorService:
    """Build vendor service with fake dependencies."""
    return VendorService(
        unit_of_work_factory=lambda: uow,
        event_dispatcher=dispatcher,
    )


def build_expense_service(
    uow: FakeExpenseUnitOfWork,
    dispatcher: CapturingEventDispatcher,
    accounting_kernel: FakeExpenseAccountingKernel | None = None,
) -> ExpenseService:
    """Build expense service with fake dependencies."""
    return ExpenseService(
        unit_of_work_factory=lambda: uow,
        event_dispatcher=dispatcher,
        accounting_kernel=accounting_kernel,
    )


async def test_vendor_lifecycle() -> None:
    """Vendor service creates, updates, deactivates, gets, and lists vendors."""
    dispatcher = CapturingEventDispatcher()
    repository = FakeVendorRepository()
    uow = FakeVendorUnitOfWork(repository)
    service = build_vendor_service(uow, dispatcher)

    created = await service.create_vendor(
        build_vendor_request(),
        business_id=uuid.uuid4(),
    )
    assert created.vendor_code.startswith("VEND-")
    assert isinstance(dispatcher.events[0], VendorCreatedEvent)

    updated = await service.update_vendor(
        created.id,
        VendorUpdate(name="Aarav Trading"),
    )
    assert updated.name == "Aarav Trading"
    assert isinstance(dispatcher.events[1], VendorUpdatedEvent)

    fetched = await service.get_vendor(created.id)
    listed = await service.list_vendors(created.business_id)
    assert fetched.id == created.id
    assert listed.items[0].id == created.id

    deactivated = await service.deactivate_vendor(created.id)
    assert deactivated.is_active is False
    assert isinstance(dispatcher.events[2], VendorDeactivatedEvent)
    assert uow.committed is True


async def test_deactivate_inactive_vendor_rejected() -> None:
    """Vendor service rejects deactivating an inactive vendor."""
    vendor = build_vendor(is_active=False)
    uow = FakeVendorUnitOfWork(FakeVendorRepository(vendor))
    service = build_vendor_service(uow, CapturingEventDispatcher())

    with pytest.raises(VendorInactiveException):
        await service.deactivate_vendor(vendor.id)

    assert uow.rolled_back is True


async def test_create_expense_calculates_totals_and_publishes_event() -> None:
    """Expense service calculates totals from lines and emits creation event."""
    vendor = build_vendor()
    dispatcher = CapturingEventDispatcher()
    uow = FakeExpenseUnitOfWork(vendor_repository=FakeVendorRepository(vendor))
    service = build_expense_service(uow, dispatcher)

    response = await service.create_expense(
        build_expense_request(vendor.id),
        business_id=vendor.business_id,
    )

    assert response.expense_number.startswith("EXP-20260501-")
    assert response.subtotal == Decimal("1000.00")
    assert response.tax_amount == Decimal("180.00")
    assert response.total_amount == Decimal("1180.00")
    assert response.lines[0].line_total == Decimal("1180.00")
    assert isinstance(dispatcher.events[0], ExpenseCreatedEvent)
    assert uow.committed is True


async def test_expense_vendor_validation() -> None:
    """Expense service validates vendor business ownership and active state."""
    inactive_vendor = build_vendor(is_active=False)
    uow = FakeExpenseUnitOfWork(
        vendor_repository=FakeVendorRepository(inactive_vendor)
    )
    service = build_expense_service(uow, CapturingEventDispatcher())

    with pytest.raises(VendorInactiveException):
        await service.create_expense(
            build_expense_request(inactive_vendor.id),
            business_id=inactive_vendor.business_id,
        )

    other_business_vendor = build_vendor()
    other_uow = FakeExpenseUnitOfWork(
        vendor_repository=FakeVendorRepository(other_business_vendor)
    )
    other_service = build_expense_service(other_uow, CapturingEventDispatcher())

    with pytest.raises(ExpenseValidationException):
        await other_service.create_expense(
            build_expense_request(other_business_vendor.id),
            business_id=uuid.uuid4(),
        )


async def test_update_expense_requires_draft_and_recalculates_lines() -> None:
    """Expense service updates only draft expenses and recalculates line totals."""
    expense = build_expense(status=ExpenseStatus.DRAFT)
    dispatcher = CapturingEventDispatcher()
    uow = FakeExpenseUnitOfWork(
        vendor_repository=FakeVendorRepository(None),
        expense_repository=FakeExpenseRepository(expense),
    )
    service = build_expense_service(uow, dispatcher)

    response = await service.update_expense(
        expense.id,
        ExpenseUpdate(
            notes="Updated",
            lines=[
                {
                    "description": "Software",
                    "quantity": "1.00",
                    "unit_cost": "200.00",
                    "tax_rate": "10.00",
                    "line_total": "1.00",
                }
            ],
        ),
    )

    assert response.notes == "Updated"
    assert response.subtotal == Decimal("200.00")
    assert response.tax_amount == Decimal("20.00")
    assert response.total_amount == Decimal("220.00")
    assert isinstance(dispatcher.events[0], ExpenseUpdatedEvent)

    paid_expense = build_expense(status=ExpenseStatus.PAID)
    invalid_uow = FakeExpenseUnitOfWork(
        vendor_repository=FakeVendorRepository(None),
        expense_repository=FakeExpenseRepository(paid_expense),
    )
    invalid_service = build_expense_service(invalid_uow, CapturingEventDispatcher())
    with pytest.raises(InvalidExpenseStatusException):
        await invalid_service.update_expense(paid_expense.id, ExpenseUpdate(notes="No"))


async def test_expense_status_transitions() -> None:
    """Expense service enforces allowed lifecycle transitions."""
    expense = build_expense(status=ExpenseStatus.DRAFT)
    dispatcher = CapturingEventDispatcher()
    accounting_kernel = FakeExpenseAccountingKernel()
    uow = FakeExpenseUnitOfWork(
        vendor_repository=FakeVendorRepository(None),
        expense_repository=FakeExpenseRepository(expense),
    )
    service = build_expense_service(uow, dispatcher, accounting_kernel)

    approved = await service.approve_expense(expense.id)
    assert approved.status == ExpenseStatus.APPROVED
    assert isinstance(dispatcher.events[0], ExpenseApprovedEvent)
    assert accounting_kernel.expense_ids == [expense.id]

    paid = await service.mark_paid(expense.id)
    assert paid.status == ExpenseStatus.PAID
    assert isinstance(dispatcher.events[1], ExpensePaidEvent)
    assert accounting_kernel.payment_expense_ids == [expense.id]

    with pytest.raises(InvalidExpenseStatusException):
        await service.cancel_expense(expense.id)

    cancellable = build_expense(status=ExpenseStatus.APPROVED)
    cancel_uow = FakeExpenseUnitOfWork(
        vendor_repository=FakeVendorRepository(None),
        expense_repository=FakeExpenseRepository(cancellable),
    )
    cancel_dispatcher = CapturingEventDispatcher()
    cancel_service = build_expense_service(cancel_uow, cancel_dispatcher)
    cancelled = await cancel_service.cancel_expense(cancellable.id)
    assert cancelled.status == ExpenseStatus.CANCELLED
    assert isinstance(cancel_dispatcher.events[0], ExpenseCancelledEvent)


async def test_get_and_list_expenses() -> None:
    """Expense service gets and lists expenses."""
    expense = build_expense(status=ExpenseStatus.DRAFT)
    uow = FakeExpenseUnitOfWork(
        vendor_repository=FakeVendorRepository(None),
        expense_repository=FakeExpenseRepository(expense),
    )
    service = build_expense_service(uow, CapturingEventDispatcher())

    fetched = await service.get_expense(expense.id)
    listed = await service.list_expenses(expense.business_id)

    assert fetched.id == expense.id
    assert listed.items[0].id == expense.id


async def test_expense_service_rolls_back_on_failure() -> None:
    """Unit of Work rolls back when expense persistence fails."""
    vendor = build_vendor()
    uow = FakeExpenseUnitOfWork(
        vendor_repository=FakeVendorRepository(vendor),
        expense_repository=FakeExpenseRepository(fail_create=True),
    )
    service = build_expense_service(uow, CapturingEventDispatcher())

    with pytest.raises(RuntimeError):
        await service.create_expense(
            build_expense_request(vendor.id),
            business_id=vendor.business_id,
        )

    assert uow.committed is False
    assert uow.rolled_back is True
