"""Canonical, deterministic sales invoice domain rules."""

from dataclasses import dataclass
from decimal import Decimal

from app.modules.gst.services import GSTSupplyType
from app.modules.sales.exceptions import (
    SalesInvalidInvoiceStatusException,
    SalesInvoiceValidationException,
)
from app.modules.sales.models import InvoiceStatus

MAX_INVOICE_NUMBER_LENGTH = 50


@dataclass(frozen=True)
class InvoiceNumber:
    """Validated, immutable invoice number value object."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip() or len(self.value) > MAX_INVOICE_NUMBER_LENGTH:
            raise SalesInvoiceValidationException("Invoice number is invalid")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class InvoiceTaxSummary:
    """Tax amounts calculated from canonical invoice lines."""

    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    cess_amount: Decimal

    @property
    def tax_amount(self) -> Decimal:
        return self.cgst_amount + self.sgst_amount + self.igst_amount

    @property
    def total(self) -> Decimal:
        return self.tax_amount + self.cess_amount


@dataclass(frozen=True)
class InvoiceTotals:
    """Authoritative invoice totals."""

    subtotal: Decimal
    discount_amount: Decimal
    taxable_amount: Decimal
    tax: InvoiceTaxSummary
    round_off: Decimal
    grand_total: Decimal


@dataclass(frozen=True)
class InvoiceLineValue:
    """Minimal values needed for deterministic calculation."""

    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    tax_rate: Decimal
    cess_rate: Decimal = Decimal("0")
    supply_type: GSTSupplyType = GSTSupplyType.INTRA_STATE


class InvoiceLifecycle:
    """Canonical state transition policy."""

    _allowed = {
        InvoiceStatus.DRAFT: {InvoiceStatus.ISSUED, InvoiceStatus.CANCELLED},
        InvoiceStatus.ISSUED: {
            InvoiceStatus.PARTIALLY_PAID,
            InvoiceStatus.PAID,
            InvoiceStatus.CANCELLED,
        },
        InvoiceStatus.PARTIALLY_PAID: {InvoiceStatus.PAID, InvoiceStatus.CANCELLED},
        InvoiceStatus.PAID: set(),
        InvoiceStatus.CANCELLED: set(),
    }

    def validate(self, current: InvoiceStatus, target: InvoiceStatus) -> None:
        if target not in self._allowed[current]:
            raise SalesInvalidInvoiceStatusException(
                "Invoice status transition is not allowed",
                details={"status": current.value, "target_status": target.value},
            )

    @staticmethod
    def ensure_editable(status: InvoiceStatus) -> None:
        if status != InvoiceStatus.DRAFT:
            raise SalesInvalidInvoiceStatusException(
                "Only draft invoices can be edited", details={"status": status.value}
            )
