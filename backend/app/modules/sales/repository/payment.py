"""Sales payment repository."""

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.repositories import BaseRepository
from app.modules.sales.models import Payment
from app.modules.sales.schemas import PaymentCreateRequest

ZERO_AMOUNT = Decimal("0.00")


class PaymentRepository(BaseRepository[Payment]):
    """Repository for invoice payment persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, Payment)

    async def create(self, request: PaymentCreateRequest) -> Payment:
        """Create a payment from request data."""
        payment = Payment(**request.model_dump())
        return await self.add(payment)

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        """Return a non-deleted payment by UUID."""
        statement = select(Payment).where(
            Payment.id == payment_id,
            Payment.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def update(
        self,
        payment: Payment,
        request: PaymentCreateRequest,
    ) -> Payment:
        """Update mutable payment fields from request data."""
        for field_name, value in request.model_dump().items():
            setattr(payment, field_name, value)
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def delete(self, payment: Payment) -> None:
        """Soft-delete a payment."""
        await super().delete(payment)

    async def list_invoice_payments(self, invoice_id: uuid.UUID) -> list[Payment]:
        """Return active payments for an invoice."""
        statement = (
            select(Payment)
            .where(
                Payment.invoice_id == invoice_id,
                Payment.is_deleted.is_(False),
            )
            .order_by(Payment.payment_date.asc(), Payment.created_at.asc())
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def total_paid(self, invoice_id: uuid.UUID) -> Decimal:
        """Return the total active payments for an invoice."""
        statement = select(func.coalesce(func.sum(Payment.amount), ZERO_AMOUNT)).where(
            Payment.invoice_id == invoice_id,
            Payment.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return Decimal(result.scalar_one())
