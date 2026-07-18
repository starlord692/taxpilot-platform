"""Expense repository."""

import uuid
from datetime import date

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.filters import FilterParams
from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.expenses.models import (
    Expense,
    ExpenseLine,
    ExpenseStatus,
    Vendor,
)
from app.modules.expenses.schemas import ExpenseCreate, ExpenseUpdate


class ExpenseRepository(BaseRepository[Expense]):
    """Repository for expense persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, Expense)

    async def create(
        self,
        request: ExpenseCreate,
        *,
        business_id: uuid.UUID,
        expense_number: str,
    ) -> Expense:
        """Create an expense with lines from request data."""
        expense_data = request.model_dump(exclude={"lines"})
        expense = Expense(
            **expense_data,
            business_id=business_id,
            expense_number=expense_number,
            lines=[
                ExpenseLine(**line.model_dump())
                for line in request.lines
            ],
        )
        return await self.add(expense)

    async def get_by_id(self, expense_id: uuid.UUID) -> Expense | None:
        """Return a non-deleted expense by UUID."""
        statement = self._base_statement().where(Expense.id == expense_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_expense_number(
        self,
        *,
        business_id: uuid.UUID,
        expense_number: str,
    ) -> Expense | None:
        """Return an expense by business-scoped expense number."""
        statement = self._base_statement().where(
            Expense.business_id == business_id,
            Expense.expense_number == expense_number,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_by_business(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        filters: FilterParams | None = None,
        sort: str | None = None,
        vendor_id: uuid.UUID | None = None,
        status: ExpenseStatus | None = None,
        expense_date_from: date | None = None,
        expense_date_to: date | None = None,
    ) -> Page[Expense]:
        """Return paginated expenses for a business with optional filters."""
        statement = self._base_statement().where(Expense.business_id == business_id)
        statement = self._apply_optional_filters(
            statement,
            vendor_id=vendor_id,
            status=status,
            expense_date_from=expense_date_from,
            expense_date_to=expense_date_to,
        )
        statement = self._apply_filters(statement, filters)
        statement = self._apply_expense_sort(statement, sort)
        return await self._paginate(statement, pagination)

    async def list_by_vendor(
        self,
        vendor_id: uuid.UUID,
        pagination: PaginationParams | None = None,
    ) -> Page[Expense]:
        """Return paginated expenses for a vendor."""
        statement = self._base_statement().where(Expense.vendor_id == vendor_id)
        return await self._paginate(statement, pagination)

    async def list_by_status(
        self,
        *,
        business_id: uuid.UUID,
        status: ExpenseStatus,
        pagination: PaginationParams | None = None,
    ) -> Page[Expense]:
        """Return paginated expenses for a business and status."""
        statement = self._base_statement().where(
            Expense.business_id == business_id,
            Expense.status == status,
        )
        return await self._paginate(statement, pagination)

    async def update(self, expense: Expense, request: ExpenseUpdate) -> Expense:
        """Update mutable expense fields from request data."""
        update_data = request.model_dump(exclude_unset=True, exclude={"lines"})
        for field_name, value in update_data.items():
            setattr(expense, field_name, value)
        self.session.add(expense)
        await self.session.flush()
        return expense

    async def delete(self, expense: Expense) -> None:
        """Soft-delete an expense."""
        await super().delete(expense)

    async def _paginate(
        self,
        statement: Select[tuple[Expense]],
        pagination: PaginationParams | None,
    ) -> Page[Expense]:
        """Paginate an expense statement."""
        params = pagination or PaginationParams()
        total = await self._count_statement(statement)
        result = await self.session.execute(
            statement.offset(params.offset).limit(params.limit)
        )
        return Page.create(
            items=list(result.scalars().unique().all()),
            total=total,
            params=params,
        )

    async def _count_statement(self, statement: Select[tuple[Expense]]) -> int:
        """Count rows from a selectable statement."""
        count_statement = select(func.count()).select_from(statement.subquery())
        result = await self.session.execute(count_statement)
        return int(result.scalar_one())

    def _base_statement(self) -> Select[tuple[Expense]]:
        """Return standard expense select with relationships loaded."""
        return (
            select(Expense)
            .options(
                selectinload(Expense.lines),
                selectinload(Expense.vendor).selectinload(Vendor.expenses),
            )
            .where(Expense.is_deleted.is_(False))
        )

    def _apply_optional_filters(
        self,
        statement: Select[tuple[Expense]],
        *,
        vendor_id: uuid.UUID | None,
        status: ExpenseStatus | None,
        expense_date_from: date | None,
        expense_date_to: date | None,
    ) -> Select[tuple[Expense]]:
        """Apply explicit expense filter options."""
        if vendor_id is not None:
            statement = statement.where(Expense.vendor_id == vendor_id)
        if status is not None:
            statement = statement.where(Expense.status == status)
        if expense_date_from is not None:
            statement = statement.where(Expense.expense_date >= expense_date_from)
        if expense_date_to is not None:
            statement = statement.where(Expense.expense_date <= expense_date_to)
        return statement

    def _apply_expense_sort(
        self,
        statement: Select[tuple[Expense]],
        sort: str | None,
    ) -> Select[tuple[Expense]]:
        """Apply supported expense sorting."""
        sort_key = sort or "-expense_date"
        direction = "desc" if sort_key.startswith("-") else "asc"
        field_name = sort_key.removeprefix("-")
        sort_columns = {
            "created_at": Expense.created_at,
            "expense_date": Expense.expense_date,
            "expense_number": Expense.expense_number,
            "status": Expense.status,
            "category": Expense.category,
            "total_amount": Expense.total_amount,
        }
        column = sort_columns.get(field_name, Expense.expense_date)
        return statement.order_by(
            column.desc() if direction == "desc" else column.asc()
        )
