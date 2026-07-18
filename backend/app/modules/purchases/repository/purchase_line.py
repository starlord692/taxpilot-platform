"""Purchase invoice line repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.repositories import BaseRepository
from app.modules.purchases.models import PurchaseInvoiceLine
from app.modules.purchases.schemas import (
    PurchaseInvoiceLineCreate,
    PurchaseInvoiceLineUpdate,
)


class PurchaseInvoiceLineRepository(BaseRepository[PurchaseInvoiceLine]):
    """Repository for purchase invoice line persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, PurchaseInvoiceLine)

    async def create(
        self,
        request: PurchaseInvoiceLineCreate,
        *,
        purchase_invoice_id: uuid.UUID,
    ) -> PurchaseInvoiceLine:
        """Create a purchase invoice line from request data."""
        line = PurchaseInvoiceLine(
            purchase_invoice_id=purchase_invoice_id,
            **request.model_dump(),
        )
        return await self.add(line)

    async def update(
        self,
        line: PurchaseInvoiceLine,
        request: PurchaseInvoiceLineUpdate,
    ) -> PurchaseInvoiceLine:
        """Update mutable purchase invoice line fields from request data."""
        for field_name, value in request.model_dump(exclude_unset=True).items():
            setattr(line, field_name, value)
        self.session.add(line)
        await self.session.flush()
        return line

    async def delete(self, line: PurchaseInvoiceLine) -> None:
        """Soft-delete a purchase invoice line."""
        await super().delete(line)

    async def get_by_id(self, line_id: uuid.UUID) -> PurchaseInvoiceLine | None:
        """Return a non-deleted purchase invoice line by UUID."""
        statement = select(PurchaseInvoiceLine).where(
            PurchaseInvoiceLine.id == line_id,
            PurchaseInvoiceLine.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_by_purchase(
        self,
        purchase_invoice_id: uuid.UUID,
    ) -> list[PurchaseInvoiceLine]:
        """Return active lines for a purchase invoice."""
        statement = (
            select(PurchaseInvoiceLine)
            .where(
                PurchaseInvoiceLine.purchase_invoice_id == purchase_invoice_id,
                PurchaseInvoiceLine.is_deleted.is_(False),
            )
            .order_by(PurchaseInvoiceLine.created_at.asc())
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())
