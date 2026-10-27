"""Sales invoice repository."""

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.sales.models import InvoiceStatus, SalesInvoice, SalesInvoiceLine
from app.modules.sales.schemas import (
    InvoiceCreateRequest,
    InvoiceLineRequest,
    InvoiceUpdateRequest,
)


class SalesInvoiceRepository(BaseRepository[SalesInvoice]):
    """Repository for sales invoice persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, SalesInvoice)

    async def create(self, request: InvoiceCreateRequest) -> SalesInvoice:
        """Create a sales invoice with lines from request data."""
        model_fields = {c.key for c in SalesInvoice.__table__.columns}
        invoice_data = {
            k: v for k, v in request.model_dump(exclude={"lines"}).items()
            if k in model_fields
        }
        line_fields = {c.key for c in SalesInvoiceLine.__table__.columns}
        invoice = SalesInvoice(
            **invoice_data,
            lines=[
                SalesInvoiceLine(
                    **{k: v for k, v in line.model_dump().items() if k in line_fields}
                )
                for line in request.lines
            ],
            payments=[],
        )
        return await self.add(invoice)

    async def update(
        self,
        invoice: SalesInvoice,
        request: InvoiceUpdateRequest,
    ) -> SalesInvoice:
        """Update mutable invoice fields from request data."""
        model_fields = {c.key for c in SalesInvoice.__table__.columns}
        update_data = {
            k: v for k, v in request.model_dump(exclude_unset=True, exclude={"lines"}).items()
            if k in model_fields
        }
        for field_name, value in update_data.items():
            setattr(invoice, field_name, value)
        self.session.add(invoice)
        await self.session.flush()
        return invoice

    async def get_by_id(self, invoice_id: uuid.UUID) -> SalesInvoice | None:
        """Return a non-deleted invoice by UUID with lines and payments loaded."""
        statement = self._detail_statement().where(SalesInvoice.id == invoice_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_invoice_number(
        self,
        *,
        business_id: uuid.UUID,
        invoice_number: str,
    ) -> SalesInvoice | None:
        """Return an invoice by business-scoped invoice number.

        Detail relationships (lines and payments) are loaded.
        """
        statement = self._detail_statement().where(
            SalesInvoice.business_id == business_id,
            SalesInvoice.invoice_number == invoice_number,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_business_invoices(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
    ) -> Page[SalesInvoice]:
        """Return paginated summary invoices for a business."""
        statement = self._summary_statement().where(
            SalesInvoice.business_id == business_id
        )
        return await self._paginate(statement, pagination)

    async def list_customer_invoices(
        self,
        customer_id: uuid.UUID,
        pagination: PaginationParams | None = None,
    ) -> Page[SalesInvoice]:
        """Return paginated summary invoices for a customer."""
        statement = self._summary_statement().where(
            SalesInvoice.customer_id == customer_id
        )
        return await self._paginate(statement, pagination)

    async def add_line(
        self,
        invoice: SalesInvoice,
        request: InvoiceLineRequest,
    ) -> SalesInvoiceLine:
        """Add a line to an invoice."""
        line_fields = {c.key for c in SalesInvoiceLine.__table__.columns}
        line_data = {
            k: v for k, v in request.model_dump().items() if k in line_fields
        }
        line = SalesInvoiceLine(invoice_id=invoice.id, **line_data)
        self.session.add(line)
        await self.session.flush()
        return line

    async def remove_line(self, line: SalesInvoiceLine) -> None:
        """Soft-delete an invoice line."""
        line.mark_deleted()
        self.session.add(line)
        await self.session.flush()

    async def mark_status(
        self,
        invoice: SalesInvoice,
        status: InvoiceStatus,
    ) -> SalesInvoice:
        """Update invoice status."""
        invoice.status = status
        self.session.add(invoice)
        await self.session.flush()
        return invoice

    async def _paginate(
        self,
        statement: Select[tuple[SalesInvoice]],
        pagination: PaginationParams | None,
    ) -> Page[SalesInvoice]:
        """Paginate an invoice statement."""
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

    async def _count_statement(self, statement: Select[tuple[SalesInvoice]]) -> int:
        """Count rows from a selectable statement using public SQLAlchemy API."""
        clean_stmt = statement.order_by(None).offset(None).limit(None)
        count_statement = select(func.count()).select_from(clean_stmt.subquery())
        result = await self.session.execute(count_statement)
        return int(result.scalar_one())

    def _summary_statement(self) -> Select[tuple[SalesInvoice]]:
        """Return summary invoice select without child collections."""
        return (
            select(SalesInvoice)
            .where(SalesInvoice.is_deleted.is_(False))
            .order_by(SalesInvoice.invoice_date.desc(), SalesInvoice.created_at.desc())
        )

    def _detail_statement(self) -> Select[tuple[SalesInvoice]]:
        """Return detail invoice select with lines and payments loaded."""
        return (
            select(SalesInvoice)
            .options(
                selectinload(SalesInvoice.lines).selectinload(SalesInvoiceLine.catalog_item),
                selectinload(SalesInvoice.payments),
            )
            .where(SalesInvoice.is_deleted.is_(False))
            .order_by(SalesInvoice.invoice_date.desc(), SalesInvoice.created_at.desc())
        )

    def _base_statement(self) -> Select[tuple[SalesInvoice]]:
        """Backwards-compatibility alias returning detail statement."""
        return self._detail_statement()
