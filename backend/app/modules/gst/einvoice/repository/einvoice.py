"""E-invoicing repository."""

import uuid

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.models.abstract.timestamp import utc_now
from app.common.repositories import BaseRepository
from app.modules.gst.einvoice.models import (
    EInvoice,
    EInvoiceQRCode,
    EInvoiceStatus,
    EWayBill,
    EWayBillStatus,
    GSTProvider,
)


class EInvoiceRepository(BaseRepository[EInvoice]):
    """Repository for e-invoice persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, EInvoice)

    async def create(self, e_invoice: EInvoice) -> EInvoice:
        """Create an e-invoice record."""
        return await self.add(e_invoice)

    async def create_qr_code(self, qr_code: EInvoiceQRCode) -> EInvoiceQRCode:
        """Create QR code data."""
        self.session.add(qr_code)
        await self.session.flush()
        return qr_code

    async def get_by_invoice_id(self, invoice_id: uuid.UUID) -> EInvoice | None:
        """Return e-invoice by sales invoice UUID."""
        result = await self.session.execute(
            self._base_statement().where(EInvoice.invoice_id == invoice_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_invoice_id(
        self,
        invoice_id: uuid.UUID,
    ) -> EInvoice | None:
        """Return non-cancelled e-invoice by sales invoice UUID."""
        result = await self.session.execute(
            self._base_statement().where(
                EInvoice.invoice_id == invoice_id,
                EInvoice.status == EInvoiceStatus.GENERATED,
            )
        )
        return result.scalar_one_or_none()

    async def get_qr_code(
        self,
        invoice_id: uuid.UUID,
    ) -> EInvoiceQRCode | None:
        """Return QR code data by sales invoice UUID."""
        result = await self.session.execute(
            select(EInvoiceQRCode).where(
                EInvoiceQRCode.invoice_id == invoice_id,
                EInvoiceQRCode.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def cancel(
        self,
        e_invoice: EInvoice,
        *,
        reason: str,
    ) -> EInvoice:
        """Mark an e-invoice as cancelled."""
        e_invoice.status = EInvoiceStatus.CANCELLED
        e_invoice.cancel_reason = reason
        e_invoice.cancelled_at = utc_now()
        self.session.add(e_invoice)
        await self.session.flush()
        return e_invoice

    def _base_statement(self) -> Select[tuple[EInvoice]]:
        """Return default e-invoice select."""
        return select(EInvoice).where(EInvoice.is_deleted.is_(False))


class EWayBillRepository(BaseRepository[EWayBill]):
    """Repository for e-way bill persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, EWayBill)

    async def create(self, eway_bill: EWayBill) -> EWayBill:
        """Create an e-way bill record."""
        return await self.add(eway_bill)

    async def get_by_invoice_id(self, invoice_id: uuid.UUID) -> EWayBill | None:
        """Return e-way bill by sales invoice UUID."""
        result = await self.session.execute(
            self._base_statement().where(EWayBill.invoice_id == invoice_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_invoice_id(
        self,
        invoice_id: uuid.UUID,
    ) -> EWayBill | None:
        """Return non-cancelled e-way bill by sales invoice UUID."""
        result = await self.session.execute(
            self._base_statement().where(
                EWayBill.invoice_id == invoice_id,
                EWayBill.status == EWayBillStatus.GENERATED,
            )
        )
        return result.scalar_one_or_none()

    async def cancel(
        self,
        eway_bill: EWayBill,
        *,
        reason: str,
    ) -> EWayBill:
        """Mark an e-way bill as cancelled."""
        eway_bill.status = EWayBillStatus.CANCELLED
        eway_bill.cancel_reason = reason
        eway_bill.cancelled_at = utc_now()
        self.session.add(eway_bill)
        await self.session.flush()
        return eway_bill

    def _base_statement(self) -> Select[tuple[EWayBill]]:
        """Return default e-way bill select."""
        return select(EWayBill).where(EWayBill.is_deleted.is_(False))


class GSTProviderRepository(BaseRepository[GSTProvider]):
    """Repository for GST provider configuration."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, GSTProvider)

    async def get_active_by_name(self, name: str) -> GSTProvider | None:
        """Return an active provider by name."""
        result = await self.session.execute(
            select(GSTProvider).where(
                GSTProvider.name == name,
                GSTProvider.is_active.is_(True),
                GSTProvider.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()
