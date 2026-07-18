"""Expense line repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.repositories import BaseRepository
from app.modules.expenses.models import ExpenseLine
from app.modules.expenses.schemas import ExpenseLineCreate, ExpenseLineUpdate


class ExpenseLineRepository(BaseRepository[ExpenseLine]):
    """Repository for expense line persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, ExpenseLine)

    async def create(
        self,
        request: ExpenseLineCreate,
        *,
        expense_id: uuid.UUID,
    ) -> ExpenseLine:
        """Create an expense line from request data."""
        line = ExpenseLine(expense_id=expense_id, **request.model_dump())
        return await self.add(line)

    async def get_by_id(self, line_id: uuid.UUID) -> ExpenseLine | None:
        """Return a non-deleted expense line by UUID."""
        statement = select(ExpenseLine).where(
            ExpenseLine.id == line_id,
            ExpenseLine.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_by_expense(self, expense_id: uuid.UUID) -> list[ExpenseLine]:
        """Return active lines for an expense."""
        statement = (
            select(ExpenseLine)
            .where(
                ExpenseLine.expense_id == expense_id,
                ExpenseLine.is_deleted.is_(False),
            )
            .order_by(ExpenseLine.created_at.asc())
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def update(
        self,
        line: ExpenseLine,
        request: ExpenseLineUpdate,
    ) -> ExpenseLine:
        """Update mutable expense line fields from request data."""
        for field_name, value in request.model_dump(exclude_unset=True).items():
            setattr(line, field_name, value)
        self.session.add(line)
        await self.session.flush()
        return line

    async def delete(self, line: ExpenseLine) -> None:
        """Soft-delete an expense line."""
        await super().delete(line)
