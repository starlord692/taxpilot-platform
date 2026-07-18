"""Expense service."""

import uuid
from collections.abc import Callable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

from app.common.events import EventDispatcher
from app.common.pagination import Page, PaginationParams
from app.modules.expenses.events import (
    ExpenseApprovedEvent,
    ExpenseCancelledEvent,
    ExpenseCreatedEvent,
    ExpensePaidEvent,
    ExpenseUpdatedEvent,
)
from app.modules.expenses.exceptions import (
    DuplicateExpenseNumberException,
    ExpenseNotFoundException,
    ExpenseValidationException,
    InvalidExpenseStatusException,
    VendorInactiveException,
    VendorNotFoundException,
)
from app.modules.expenses.models import Expense, ExpenseLine, ExpenseStatus, Vendor
from app.modules.expenses.schemas import (
    ExpenseCreate,
    ExpenseLineCreate,
    ExpenseResponse,
    ExpenseUpdate,
)
from app.modules.gst.services import (
    GSTCalculationLineInput,
    GSTCalculationService,
    GSTSupplyType,
)

MONEY_PLACES = Decimal("0.01")


class ExpenseVendorRepository(Protocol):
    """Vendor repository behavior required by expense service."""

    async def get_by_id(self, vendor_id: uuid.UUID) -> Vendor | None:
        """Return a vendor by UUID."""
        ...


class ExpensePersistenceRepository(Protocol):
    """Expense repository behavior required by expense service."""

    async def create(
        self,
        request: ExpenseCreate,
        *,
        business_id: uuid.UUID,
        expense_number: str,
    ) -> Expense:
        """Create an expense."""
        ...

    async def get_by_id(self, expense_id: uuid.UUID) -> Expense | None:
        """Return an expense by UUID."""
        ...

    async def get_by_expense_number(
        self,
        *,
        business_id: uuid.UUID,
        expense_number: str,
    ) -> Expense | None:
        """Return an expense by number."""
        ...

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
        """Return expenses for a business."""
        ...

    async def update(self, expense: Expense, request: ExpenseUpdate) -> Expense:
        """Update an expense."""
        ...


class ExpenseLinePersistenceRepository(Protocol):
    """Expense line repository behavior required by expense service."""

    async def create(
        self,
        request: ExpenseLineCreate,
        *,
        expense_id: uuid.UUID,
    ) -> ExpenseLine:
        """Create an expense line."""
        ...

    async def delete(self, line: ExpenseLine) -> None:
        """Soft-delete an expense line."""
        ...


class ExpenseAccountingKernel(Protocol):
    """Accounting behavior required by expense lifecycle integration."""

    async def record_expense(self, expense_id: uuid.UUID) -> object:
        """Post an approved expense to accounting."""
        ...

    async def record_expense_payment(self, expense_id: uuid.UUID) -> object:
        """Post a paid expense payment to accounting."""
        ...


class ExpenseUnitOfWork(Protocol):
    """Unit of Work contract required by expense service."""

    vendors: ExpenseVendorRepository
    expenses: ExpensePersistenceRepository
    expense_lines: ExpenseLinePersistenceRepository

    async def __aenter__(self) -> "ExpenseUnitOfWork":
        """Enter the expense transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the expense transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit expense changes."""
        ...


UnitOfWorkFactory = Callable[[], ExpenseUnitOfWork]


class ExpenseService:
    """Coordinate expense lifecycle operations."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
        accounting_kernel: ExpenseAccountingKernel | None = None,
        gst_calculation_service: GSTCalculationService | None = None,
    ) -> None:
        """Initialize service dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher
        self._accounting_kernel = accounting_kernel
        self._gst_calculation_service = (
            gst_calculation_service or GSTCalculationService(event_dispatcher)
        )

    async def create_expense(
        self,
        request: ExpenseCreate,
        *,
        business_id: uuid.UUID,
    ) -> ExpenseResponse:
        """Create an expense, calculate totals, and publish an event."""
        validated_request = ExpenseCreate.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            await self._validate_vendor(uow, validated_request.vendor_id, business_id)
            expense_number = await self._generate_unique_expense_number(
                uow,
                business_id,
                validated_request.expense_date,
            )
            prepared_request = self._prepare_create_request(validated_request)
            expense = await uow.expenses.create(
                prepared_request,
                business_id=business_id,
                expense_number=expense_number,
            )
            await self._event_dispatcher.dispatch(
                ExpenseCreatedEvent(
                    expense_id=expense.id,
                    business_id=expense.business_id,
                )
            )
            await uow.commit()
        return ExpenseResponse.model_validate(expense)

    async def update_expense(
        self,
        expense_id: uuid.UUID,
        request: ExpenseUpdate,
    ) -> ExpenseResponse:
        """Update a draft expense and publish an event."""
        validated_request = ExpenseUpdate.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            expense = await self._get_existing_expense(uow, expense_id)
            self._ensure_editable(expense)
            await self._validate_vendor(
                uow,
                validated_request.vendor_id,
                expense.business_id,
            )
            prepared_request = self._prepare_update_request(expense, validated_request)
            expense = await uow.expenses.update(expense, prepared_request)
            if prepared_request.lines is not None:
                for line in list(expense.lines):
                    await uow.expense_lines.delete(line)
                expense.lines = []
                for line_request in self._line_updates_to_create_requests(
                    prepared_request
                ):
                    line = await uow.expense_lines.create(
                        line_request,
                        expense_id=expense.id,
                    )
                    expense.lines.append(line)
            await self._event_dispatcher.dispatch(
                ExpenseUpdatedEvent(
                    expense_id=expense.id,
                    business_id=expense.business_id,
                )
            )
            await uow.commit()
        return ExpenseResponse.model_validate(expense)

    async def approve_expense(self, expense_id: uuid.UUID) -> ExpenseResponse:
        """Approve a draft expense."""
        response = await self._transition_expense(
            expense_id,
            target_status=ExpenseStatus.APPROVED,
            allowed_statuses={ExpenseStatus.DRAFT},
            event_name="approved",
        )
        if self._accounting_kernel is not None:
            await self._accounting_kernel.record_expense(expense_id)
        return response

    async def mark_paid(self, expense_id: uuid.UUID) -> ExpenseResponse:
        """Mark an approved expense as paid."""
        response = await self._transition_expense(
            expense_id,
            target_status=ExpenseStatus.PAID,
            allowed_statuses={ExpenseStatus.APPROVED},
            event_name="paid",
        )
        if self._accounting_kernel is not None:
            await self._accounting_kernel.record_expense_payment(expense_id)
        return response

    async def cancel_expense(self, expense_id: uuid.UUID) -> ExpenseResponse:
        """Cancel a draft or approved expense."""
        return await self._transition_expense(
            expense_id,
            target_status=ExpenseStatus.CANCELLED,
            allowed_statuses={ExpenseStatus.DRAFT, ExpenseStatus.APPROVED},
            event_name="cancelled",
        )

    async def get_expense(self, expense_id: uuid.UUID) -> ExpenseResponse:
        """Return an expense by UUID."""
        async with self._unit_of_work_factory() as uow:
            expense = await self._get_existing_expense(uow, expense_id)
            await uow.commit()
        return ExpenseResponse.model_validate(expense)

    async def list_expenses(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        sort: str | None = None,
        vendor_id: uuid.UUID | None = None,
        status: ExpenseStatus | None = None,
        expense_date_from: date | None = None,
        expense_date_to: date | None = None,
    ) -> Page[ExpenseResponse]:
        """Return paginated expenses for a business."""
        async with self._unit_of_work_factory() as uow:
            page = await uow.expenses.list_by_business(
                business_id,
                pagination,
                sort=sort,
                vendor_id=vendor_id,
                status=status,
                expense_date_from=expense_date_from,
                expense_date_to=expense_date_to,
            )
            await uow.commit()
        return Page.create(
            items=[ExpenseResponse.model_validate(expense) for expense in page.items],
            total=page.meta.total,
            params=pagination or PaginationParams(),
        )

    async def _transition_expense(
        self,
        expense_id: uuid.UUID,
        *,
        target_status: ExpenseStatus,
        allowed_statuses: set[ExpenseStatus],
        event_name: str,
    ) -> ExpenseResponse:
        """Apply an expense lifecycle status transition."""
        async with self._unit_of_work_factory() as uow:
            expense = await self._get_existing_expense(uow, expense_id)
            if expense.status not in allowed_statuses:
                raise InvalidExpenseStatusException(
                    "Expense status transition is not allowed",
                    details={
                        "expense_id": str(expense_id),
                        "status": expense.status.value,
                        "target_status": target_status.value,
                    },
                )
            expense = await uow.expenses.update(
                expense,
                ExpenseUpdate(status=target_status),
            )
            await self._dispatch_status_event(expense, event_name)
            await uow.commit()
        return ExpenseResponse.model_validate(expense)

    async def _get_existing_expense(
        self,
        uow: ExpenseUnitOfWork,
        expense_id: uuid.UUID,
    ) -> Expense:
        """Return an expense or raise not found."""
        expense = await uow.expenses.get_by_id(expense_id)
        if expense is None:
            raise ExpenseNotFoundException(
                "Expense not found",
                details={"expense_id": str(expense_id)},
            )
        return expense

    async def _validate_vendor(
        self,
        uow: ExpenseUnitOfWork,
        vendor_id: uuid.UUID | None,
        business_id: uuid.UUID,
    ) -> None:
        """Validate vendor belongs to the business and is active."""
        if vendor_id is None:
            return
        vendor = await uow.vendors.get_by_id(vendor_id)
        if vendor is None:
            raise VendorNotFoundException(
                "Vendor not found",
                details={"vendor_id": str(vendor_id)},
            )
        if vendor.business_id != business_id:
            raise ExpenseValidationException(
                "Vendor does not belong to expense business",
                details={
                    "business_id": str(business_id),
                    "vendor_id": str(vendor_id),
                },
            )
        if not vendor.is_active:
            raise VendorInactiveException(
                "Inactive vendors cannot be used for expenses",
                details={"vendor_id": str(vendor_id)},
            )

    def _ensure_editable(self, expense: Expense) -> None:
        """Raise when an expense cannot be edited."""
        if expense.status != ExpenseStatus.DRAFT:
            raise InvalidExpenseStatusException(
                "Only draft expenses may be edited",
                details={
                    "expense_id": str(expense.id),
                    "status": expense.status.value,
                },
            )

    async def _generate_unique_expense_number(
        self,
        uow: ExpenseUnitOfWork,
        business_id: uuid.UUID,
        expense_date: date,
    ) -> str:
        """Generate a unique business-scoped expense number."""
        for _attempt in range(10):
            expense_number = f"EXP-{expense_date:%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
            existing = await uow.expenses.get_by_expense_number(
                business_id=business_id,
                expense_number=expense_number,
            )
            if existing is None:
                return expense_number
        raise DuplicateExpenseNumberException(
            "Unable to generate a unique expense number",
            details={"business_id": str(business_id)},
        )

    def _prepare_create_request(self, request: ExpenseCreate) -> ExpenseCreate:
        """Calculate expense totals before persistence."""
        totals = self._calculate_totals(request.lines)
        return request.model_copy(update={"status": ExpenseStatus.DRAFT, **totals})

    def _prepare_update_request(
        self,
        expense: Expense,
        request: ExpenseUpdate,
    ) -> ExpenseUpdate:
        """Calculate expense update totals when lines are supplied."""
        _ = expense
        if request.lines is None:
            return request
        line_requests = self._line_updates_to_create_requests(request)
        totals = self._calculate_totals(line_requests)
        return request.model_copy(update=totals)

    def _line_updates_to_create_requests(
        self,
        request: ExpenseUpdate,
    ) -> list[ExpenseLineCreate]:
        """Convert full line update payloads to create payloads."""
        if request.lines is None:
            return []
        line_requests: list[ExpenseLineCreate] = []
        for line in request.lines:
            if (
                line.description is None
                or line.quantity is None
                or line.unit_cost is None
                or line.line_total is None
            ):
                raise ExpenseValidationException(
                    "Updated expense lines must include description, quantity, "
                    "unit_cost, and line_total"
                )
            line_requests.append(
                ExpenseLineCreate(
                    description=line.description,
                    quantity=line.quantity,
                    unit_cost=line.unit_cost,
                    tax_rate=line.tax_rate or Decimal("0.00"),
                    cgst_amount=line.cgst_amount or Decimal("0.00"),
                    sgst_amount=line.sgst_amount or Decimal("0.00"),
                    igst_amount=line.igst_amount or Decimal("0.00"),
                    cess_amount=line.cess_amount or Decimal("0.00"),
                    line_total=line.line_total,
                )
            )
        return line_requests

    def _calculate_totals(
        self,
        lines: list[ExpenseLineCreate],
    ) -> dict[str, Decimal | list[ExpenseLineCreate]]:
        """Calculate expense line totals and aggregate totals."""
        if not lines:
            raise ExpenseValidationException("Expense must include at least one line")

        prepared_lines: list[ExpenseLineCreate] = []
        subtotal = Decimal("0.00")
        tax_amount = Decimal("0.00")
        for line in lines:
            line_subtotal = self._money(line.quantity * line.unit_cost)
            breakdown = self._gst_calculation_service.calculate_line(
                GSTCalculationLineInput(
                    description=line.description,
                    quantity=Decimal("1.00"),
                    unit_amount=line_subtotal,
                    tax_rate=line.tax_rate,
                    supply_type=GSTSupplyType.INTRA_STATE,
                )
            )
            prepared_lines.append(
                line.model_copy(
                    update={
                        "cgst_amount": breakdown.cgst_amount,
                        "sgst_amount": breakdown.sgst_amount,
                        "igst_amount": breakdown.igst_amount,
                        "cess_amount": breakdown.cess_amount,
                        "line_total": breakdown.line_total,
                    }
                )
            )
            subtotal += line_subtotal
            tax_amount += breakdown.tax_amount

        subtotal = self._money(subtotal)
        tax_amount = self._money(tax_amount)
        return {
            "lines": prepared_lines,
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "total_amount": self._money(subtotal + tax_amount),
        }

    async def _dispatch_status_event(
        self,
        expense: Expense,
        event_name: str,
    ) -> None:
        """Publish an expense status event."""
        events = {
            "approved": ExpenseApprovedEvent,
            "paid": ExpensePaidEvent,
            "cancelled": ExpenseCancelledEvent,
        }
        event_type = events[event_name]
        await self._event_dispatcher.dispatch(
            event_type(expense_id=expense.id, business_id=expense.business_id)
        )

    def _money(self, value: Decimal) -> Decimal:
        """Round monetary values to two decimal places."""
        return value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)
