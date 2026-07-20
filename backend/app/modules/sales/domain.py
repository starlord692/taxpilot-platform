"""Canonical, deterministic sales invoice domain rules."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.modules.sales.exceptions import (
    SalesInvalidInvoiceStatusException,
    SalesInvoiceValidationException,
)
from app.modules.sales.models import InvoiceStatus

MONEY = Decimal("0.01")
HUNDRED = Decimal("100")
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

    tax_amount: Decimal
    cess_amount: Decimal


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


class InvoiceTotalsCalculator:
    """Single source of truth for sales totals."""

    def calculate(
        self, lines: list[InvoiceLineValue], round_off: Decimal = Decimal("0")
    ) -> InvoiceTotals:
        if not lines:
            raise SalesInvoiceValidationException(
                "Invoice must include at least one line"
            )
        subtotal = discount = tax = cess = Decimal("0")
        for line in lines:
            if line.quantity <= 0 or line.unit_price < 0:
                raise SalesInvoiceValidationException(
                    "Quantity must be positive and unit price non-negative"
                )
            gross = self._money(line.quantity * line.unit_price)
            line_discount = self._money(line.discount)
            if line_discount < 0 or line_discount > gross:
                raise SalesInvoiceValidationException(
                    "Line discount must be between zero and line gross amount"
                )
            taxable = self._money(gross - line_discount)
            if not Decimal("0") <= line.tax_rate <= Decimal("100") or not Decimal(
                "0"
            ) <= line.cess_rate <= Decimal("100"):
                raise SalesInvoiceValidationException(
                    "Tax and cess rates must be between zero and 100"
                )
            subtotal += gross
            discount += line_discount
            tax += self._money(taxable * line.tax_rate / HUNDRED)
            cess += self._money(taxable * line.cess_rate / HUNDRED)
        taxable_total = self._money(subtotal - discount)
        rounded = self._money(round_off)
        grand_total = self._money(taxable_total + tax + cess + rounded)
        if grand_total < 0:
            raise SalesInvoiceValidationException("Grand total cannot be negative")
        return InvoiceTotals(
            self._money(subtotal),
            self._money(discount),
            taxable_total,
            InvoiceTaxSummary(self._money(tax), self._money(cess)),
            rounded,
            grand_total,
        )

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(MONEY, rounding=ROUND_HALF_UP)


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
