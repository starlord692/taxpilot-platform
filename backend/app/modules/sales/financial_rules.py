"""Deterministic monetary rules for canonical Sales invoices."""

import uuid
from collections.abc import Sequence
from datetime import date, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Protocol

from app.modules.gst.services import (
    GSTCalculationLineInput,
    GSTCalculationService,
    GSTLineBreakdown,
    GSTSupplyType,
)
from app.modules.sales.domain import InvoiceLineValue, InvoiceTaxSummary, InvoiceTotals
from app.modules.sales.exceptions import SalesInvoiceValidationException

MONEY = Decimal("0.01")
WHOLE = Decimal("1")
CURRENCY_CODE_LENGTH = 3
SUPPORTED_PAYMENT_TERMS = frozenset({0, 7, 15, 30, 45, 60})


class RoundOffPolicy(StrEnum):
    NONE = "none"
    NEAREST_WHOLE = "nearest_whole"
    DOWN = "down"
    UP = "up"


class CreditValidationHook(Protocol):
    async def validate(
        self,
        *,
        business_id: uuid.UUID,
        customer_id: uuid.UUID,
        grand_total: Decimal,
        currency: str,
    ) -> None: ...


class StoredFinancialLine(Protocol):
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    tax_rate: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    cess_amount: Decimal


class StoredFinancialInvoice(Protocol):
    lines: Sequence[StoredFinancialLine]
    subtotal: Decimal
    discount_amount: Decimal
    taxable_amount: Decimal
    tax_amount: Decimal
    round_off: Decimal
    total_amount: Decimal
    invoice_date: date
    due_date: date | None


class SalesFinancialRulesEngine:
    """Single authority for invoice calculation and reconciliation."""

    def __init__(
        self,
        *,
        gst: GSTCalculationService | None = None,
        round_off_policy: RoundOffPolicy = RoundOffPolicy.NONE,
    ) -> None:
        self._gst = gst or GSTCalculationService()
        self.round_off_policy = round_off_policy

    def calculate(self, lines: list[InvoiceLineValue]) -> InvoiceTotals:
        if not lines:
            raise SalesInvoiceValidationException(
                "Invoice must include at least one line"
            )
        subtotal = discount = taxable = cgst = sgst = igst = cess = Decimal("0")
        for line in lines:
            if line.quantity <= 0 or line.unit_price < 0:
                raise SalesInvoiceValidationException(
                    "Quantity must be positive and unit price non-negative"
                )
            gross = self._money(line.quantity * line.unit_price)
            if line.discount < 0 or line.discount > gross:
                raise SalesInvoiceValidationException(
                    "Line discount must be between zero and line gross amount"
                )
            breakdown = self._gst.calculate_line(
                GSTCalculationLineInput(
                    quantity=line.quantity,
                    unit_amount=line.unit_price,
                    discount=line.discount,
                    tax_rate=line.tax_rate,
                    cess_rate=line.cess_rate,
                    supply_type=line.supply_type,
                )
            )
            subtotal += gross
            discount += self._money(line.discount)
            taxable += breakdown.taxable_value
            cgst += breakdown.cgst_amount
            sgst += breakdown.sgst_amount
            igst += breakdown.igst_amount
            cess += breakdown.cess_amount
        tax = InvoiceTaxSummary(
            self._money(cgst), self._money(sgst), self._money(igst), self._money(cess)
        )
        unrounded = self._money(taxable + tax.total)
        round_off = self._round_off(unrounded)
        return InvoiceTotals(
            self._money(subtotal),
            self._money(discount),
            self._money(taxable),
            tax,
            round_off,
            self._money(unrounded + round_off),
        )

    def calculate_line(self, line: InvoiceLineValue) -> GSTLineBreakdown:
        """Return the authoritative GST component breakdown for one line."""
        return self._gst.calculate_line(
            GSTCalculationLineInput(
                quantity=line.quantity,
                unit_amount=line.unit_price,
                discount=line.discount,
                tax_rate=line.tax_rate,
                cess_rate=line.cess_rate,
                supply_type=line.supply_type,
            )
        )

    def legacy_tax_components(self, line: StoredFinancialLine) -> GSTLineBreakdown:
        """Reconstruct GST components missing from pre-engine canonical drafts."""
        return self._gst.calculate_line(
            GSTCalculationLineInput(
                quantity=line.quantity,
                unit_amount=line.unit_price,
                discount=line.discount,
                tax_rate=line.tax_rate,
                cess_rate=Decimal("0"),
                supply_type=GSTSupplyType.INTRA_STATE,
            )
        )

    def due_date(self, invoice_date: date, payment_terms_days: int) -> date:
        if payment_terms_days not in SUPPORTED_PAYMENT_TERMS:
            raise SalesInvoiceValidationException(
                "Unsupported payment terms",
                details={"payment_terms_days": payment_terms_days},
            )
        return invoice_date + timedelta(days=payment_terms_days)

    def validate_due_date(self, invoice_date: date, due_date: date | None) -> None:
        if due_date is not None and due_date < invoice_date:
            raise SalesInvoiceValidationException(
                "Due date cannot precede invoice date"
            )

    def validate_currency(self, requested: str | None, configured: str) -> str:
        currency = (requested or configured).upper()
        if len(currency) != CURRENCY_CODE_LENGTH or not currency.isalpha():
            raise SalesInvoiceValidationException(
                "Currency must be a valid ISO-4217 code"
            )
        if currency != configured.upper():
            raise SalesInvoiceValidationException(
                "Invoice currency must match business currency",
                details={
                    "invoice_currency": currency,
                    "business_currency": configured.upper(),
                },
            )
        return currency

    def reconcile(self, invoice: StoredFinancialInvoice) -> None:
        lines = invoice.lines
        if not lines:
            raise SalesInvoiceValidationException("Issued invoice must contain lines")
        subtotal = sum(
            (self._money(line.quantity * line.unit_price) for line in lines),
            Decimal("0"),
        )
        discount = sum((self._money(line.discount) for line in lines), Decimal("0"))
        taxable = self._money(subtotal - discount)
        tax = self._money(
            sum(
                (
                    line.cgst_amount
                    + line.sgst_amount
                    + line.igst_amount
                    + line.cess_amount
                    for line in lines
                ),
                Decimal("0"),
            )
        )
        expected_total = self._money(taxable + tax + invoice.round_off)
        expected = {
            "subtotal": self._money(subtotal),
            "discount_amount": self._money(discount),
            "taxable_amount": taxable,
            "tax_amount": tax,
            "total_amount": expected_total,
        }
        mismatches = [
            name
            for name, value in expected.items()
            if self._money(getattr(invoice, name)) != value
        ]
        if mismatches:
            raise SalesInvoiceValidationException(
                "Invoice financial values do not reconcile",
                details={"fields": mismatches},
            )
        if any(value < 0 for value in expected.values()):
            raise SalesInvoiceValidationException(
                "Invoice monetary values cannot be negative"
            )
        self.validate_due_date(invoice.invoice_date, invoice.due_date)

    def _round_off(self, value: Decimal) -> Decimal:
        if self.round_off_policy == RoundOffPolicy.NONE:
            return Decimal("0.00")
        rounding = {
            RoundOffPolicy.NEAREST_WHOLE: ROUND_HALF_UP,
            RoundOffPolicy.DOWN: ROUND_FLOOR,
            RoundOffPolicy.UP: ROUND_CEILING,
        }[self.round_off_policy]
        return self._money(value.quantize(WHOLE, rounding=rounding) - value)

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(MONEY, rounding=ROUND_HALF_UP)
