"""GST compliance read repository."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.expenses.models import Expense, ExpenseStatus
from app.modules.purchases.models import PurchaseInvoice, PurchaseStatus
from app.modules.sales.models import InvoiceStatus, SalesInvoice


class GSTComplianceRepository:
    """Read-only repository for GST compliance source documents."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with an async session."""
        self._session = session

    async def list_sales(
        self,
        *,
        business_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> list[SalesInvoice]:
        """Return sales invoices for a GST period."""
        result = await self._session.execute(
            select(SalesInvoice)
            .options(
                selectinload(SalesInvoice.lines),
                selectinload(SalesInvoice.customer),
            )
            .where(
                SalesInvoice.business_id == business_id,
                SalesInvoice.invoice_date >= start_date,
                SalesInvoice.invoice_date <= end_date,
                SalesInvoice.status.in_(
                    [
                        InvoiceStatus.ISSUED,
                        InvoiceStatus.PARTIALLY_PAID,
                        InvoiceStatus.PAID,
                    ]
                ),
                SalesInvoice.is_deleted.is_(False),
            )
        )
        return list(result.scalars().unique().all())

    async def list_purchases(
        self,
        *,
        business_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> list[PurchaseInvoice]:
        """Return purchase invoices for a GST period."""
        result = await self._session.execute(
            select(PurchaseInvoice)
            .options(
                selectinload(PurchaseInvoice.lines),
                selectinload(PurchaseInvoice.supplier),
            )
            .where(
                PurchaseInvoice.business_id == business_id,
                PurchaseInvoice.invoice_date >= start_date,
                PurchaseInvoice.invoice_date <= end_date,
                PurchaseInvoice.status.in_(
                    [
                        PurchaseStatus.APPROVED,
                        PurchaseStatus.RECEIVED,
                        PurchaseStatus.PAID,
                    ]
                ),
                PurchaseInvoice.is_deleted.is_(False),
            )
        )
        return list(result.scalars().unique().all())

    async def list_expenses(
        self,
        *,
        business_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> list[Expense]:
        """Return expenses for a GST period."""
        result = await self._session.execute(
            select(Expense)
            .options(selectinload(Expense.lines), selectinload(Expense.vendor))
            .where(
                Expense.business_id == business_id,
                Expense.expense_date >= start_date,
                Expense.expense_date <= end_date,
                Expense.status.in_([ExpenseStatus.APPROVED, ExpenseStatus.PAID]),
                Expense.is_deleted.is_(False),
            )
        )
        return list(result.scalars().unique().all())
