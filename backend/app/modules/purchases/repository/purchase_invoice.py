"""Purchase invoice repository."""

import uuid
from datetime import date
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.filters import FilterParams
from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.purchases.models import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchaseStatus,
    Supplier,
)
from app.modules.purchases.schemas import PurchaseInvoiceCreate, PurchaseInvoiceUpdate


class PurchaseInvoiceRepository(BaseRepository[PurchaseInvoice]):
    """Repository for purchase invoice persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, PurchaseInvoice)

    async def create(
        self,
        request: PurchaseInvoiceCreate,
        *,
        business_id: uuid.UUID,
        purchase_number: str,
    ) -> PurchaseInvoice:
        """Create a purchase invoice with lines from request data."""
        invoice_data = request.model_dump(exclude={"lines"})
        purchase_invoice = PurchaseInvoice(
            **invoice_data,
            business_id=business_id,
            purchase_number=purchase_number,
            lines=[
                PurchaseInvoiceLine(**line.model_dump())
                for line in request.lines
            ],
        )
        return await self.add(purchase_invoice)

    async def update(
        self,
        purchase_invoice: PurchaseInvoice,
        request: PurchaseInvoiceUpdate,
    ) -> PurchaseInvoice:
        """Update mutable purchase invoice fields from request data."""
        update_data = request.model_dump(exclude_unset=True, exclude={"lines"})
        for field_name, value in update_data.items():
            setattr(purchase_invoice, field_name, value)
        self.session.add(purchase_invoice)
        await self.session.flush()
        return purchase_invoice

    async def delete(self, purchase_invoice: PurchaseInvoice) -> None:
        """Soft-delete a purchase invoice."""
        await super().delete(purchase_invoice)

    async def get_by_id(
        self,
        purchase_invoice_id: uuid.UUID,
    ) -> PurchaseInvoice | None:
        """Return a non-deleted purchase invoice by UUID."""
        statement = self._base_statement().where(
            PurchaseInvoice.id == purchase_invoice_id
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_purchase_number(
        self,
        *,
        business_id: uuid.UUID,
        purchase_number: str,
    ) -> PurchaseInvoice | None:
        """Return a purchase invoice by business-scoped purchase number."""
        statement = self._base_statement().where(
            PurchaseInvoice.business_id == business_id,
            PurchaseInvoice.purchase_number == purchase_number,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_invoice_number(
        self,
        *,
        business_id: uuid.UUID,
        invoice_number: str,
    ) -> PurchaseInvoice | None:
        """Return a purchase invoice by supplier invoice number."""
        statement = self._base_statement().where(
            PurchaseInvoice.business_id == business_id,
            PurchaseInvoice.invoice_number == invoice_number,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list(  # type: ignore[override]
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        filters: FilterParams | None = None,
        sort: str | None = None,
        supplier_id: uuid.UUID | None = None,
        status: PurchaseStatus | None = None,
        invoice_date_from: date | None = None,
        invoice_date_to: date | None = None,
        due_date_from: date | None = None,
        due_date_to: date | None = None,
        purchase_number: str | None = None,
        invoice_number: str | None = None,
    ) -> Page[PurchaseInvoice]:
        """Return paginated purchase invoices with optional filters."""
        statement = self._base_statement().where(
            PurchaseInvoice.business_id == business_id
        )
        statement = self._apply_optional_filters(
            statement,
            supplier_id=supplier_id,
            status=status,
            invoice_date_from=invoice_date_from,
            invoice_date_to=invoice_date_to,
            due_date_from=due_date_from,
            due_date_to=due_date_to,
            purchase_number=purchase_number,
            invoice_number=invoice_number,
        )
        statement = self._apply_filters(statement, filters)
        statement = self._apply_purchase_sort(statement, sort)
        return await self._paginate(statement, pagination)

    async def search(
        self,
        *,
        business_id: uuid.UUID,
        query: str,
        pagination: PaginationParams | None = None,
    ) -> Page[PurchaseInvoice]:
        """Search purchase invoices by purchase number, invoice number, or notes."""
        search_pattern = f"%{query.strip()}%"
        statement = self._base_statement().where(
            PurchaseInvoice.business_id == business_id,
            or_(
                PurchaseInvoice.purchase_number.ilike(search_pattern),
                PurchaseInvoice.invoice_number.ilike(search_pattern),
                PurchaseInvoice.notes.ilike(search_pattern),
            ),
        )
        statement = self._apply_purchase_sort(statement, "-invoice_date")
        return await self._paginate(statement, pagination)

    async def exists(  # type: ignore[override]
        self,
        *,
        business_id: uuid.UUID,
        purchase_number: str | None = None,
        invoice_number: str | None = None,
    ) -> bool:
        """Return whether a purchase invoice exists for supplied business keys."""
        statement = self._base_statement().where(
            PurchaseInvoice.business_id == business_id
        )
        if purchase_number is not None:
            statement = statement.where(
                PurchaseInvoice.purchase_number == purchase_number
            )
        if invoice_number is not None:
            statement = statement.where(
                PurchaseInvoice.invoice_number == invoice_number
            )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def _paginate(
        self,
        statement: Select[tuple[PurchaseInvoice]],
        pagination: PaginationParams | None,
    ) -> Page[PurchaseInvoice]:
        """Paginate a purchase invoice statement."""
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

    async def _count_statement(
        self,
        statement: Select[tuple[PurchaseInvoice]],
    ) -> int:
        """Count rows from a selectable statement."""
        count_statement = select(func.count()).select_from(statement.subquery())
        result = await self.session.execute(count_statement)
        return int(result.scalar_one())

    def _base_statement(self) -> Select[tuple[PurchaseInvoice]]:
        """Return standard purchase invoice select with relationships loaded."""
        return (
            select(PurchaseInvoice)
            .options(
                selectinload(PurchaseInvoice.lines),
                selectinload(PurchaseInvoice.supplier),
            )
            .where(PurchaseInvoice.is_deleted.is_(False))
        )

    def _apply_optional_filters(
        self,
        statement: Select[tuple[PurchaseInvoice]],
        *,
        supplier_id: uuid.UUID | None,
        status: PurchaseStatus | None,
        invoice_date_from: date | None,
        invoice_date_to: date | None,
        due_date_from: date | None,
        due_date_to: date | None,
        purchase_number: str | None,
        invoice_number: str | None,
    ) -> Select[tuple[PurchaseInvoice]]:
        """Apply explicit purchase invoice filter options."""
        if supplier_id is not None:
            statement = statement.where(PurchaseInvoice.supplier_id == supplier_id)
        if status is not None:
            statement = statement.where(PurchaseInvoice.status == status)
        if invoice_date_from is not None:
            statement = statement.where(
                PurchaseInvoice.invoice_date >= invoice_date_from
            )
        if invoice_date_to is not None:
            statement = statement.where(PurchaseInvoice.invoice_date <= invoice_date_to)
        if due_date_from is not None:
            statement = statement.where(PurchaseInvoice.due_date >= due_date_from)
        if due_date_to is not None:
            statement = statement.where(PurchaseInvoice.due_date <= due_date_to)
        if purchase_number is not None:
            statement = statement.where(
                PurchaseInvoice.purchase_number == purchase_number
            )
        if invoice_number is not None:
            statement = statement.where(
                PurchaseInvoice.invoice_number == invoice_number
            )
        return statement

    def _apply_purchase_sort(
        self,
        statement: Select[tuple[PurchaseInvoice]],
        sort: str | None,
    ) -> Select[tuple[PurchaseInvoice]]:
        """Apply supported purchase invoice sorting."""
        sort_key = sort or "-invoice_date"
        direction = "desc" if sort_key.startswith("-") else "asc"
        field_name = sort_key.removeprefix("-")
        if field_name == "supplier_name":
            statement = statement.join(PurchaseInvoice.supplier)
            column: Any = Supplier.name
        else:
            sort_columns = {
                "created_at": PurchaseInvoice.created_at,
                "invoice_date": PurchaseInvoice.invoice_date,
                "due_date": PurchaseInvoice.due_date,
                "purchase_number": PurchaseInvoice.purchase_number,
            }
            column = sort_columns.get(field_name, PurchaseInvoice.invoice_date)
        return statement.order_by(
            column.desc() if direction == "desc" else column.asc()
        )
