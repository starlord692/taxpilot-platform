"""Sales Financial Rules Engine tests."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.modules.gst.services import GSTSupplyType
from app.modules.sales.domain import InvoiceLineValue
from app.modules.sales.exceptions import SalesInvoiceValidationException
from app.modules.sales.financial_rules import RoundOffPolicy, SalesFinancialRulesEngine


def line(
    *,
    supply: GSTSupplyType = GSTSupplyType.INTRA_STATE,
    discount: str = "0",
    cess: str = "0",
) -> InvoiceLineValue:
    return InvoiceLineValue(
        Decimal("2"),
        Decimal("100"),
        Decimal(discount),
        Decimal("18"),
        Decimal(cess),
        supply,
    )


def test_intra_state_tax_splits_cgst_and_sgst() -> None:
    totals = SalesFinancialRulesEngine().calculate([line()])
    assert totals.tax.cgst_amount == Decimal("18.00")
    assert totals.tax.sgst_amount == Decimal("18.00")
    assert totals.tax.igst_amount == Decimal("0.00")
    assert totals.grand_total == Decimal("236.00")


def test_inter_state_tax_uses_igst() -> None:
    totals = SalesFinancialRulesEngine().calculate(
        [line(supply=GSTSupplyType.INTER_STATE)]
    )
    assert totals.tax.igst_amount == Decimal("36.00")
    assert totals.tax.cgst_amount == totals.tax.sgst_amount == Decimal("0.00")


def test_discount_and_cess_are_centralized() -> None:
    totals = SalesFinancialRulesEngine().calculate([line(discount="10", cess="1")])
    assert totals.discount_amount == Decimal("10.00")
    assert totals.tax.cess_amount == Decimal("1.90")
    assert totals.grand_total == Decimal("226.10")


@pytest.mark.parametrize(
    ("policy", "expected"),
    [
        (RoundOffPolicy.NONE, "0.00"),
        (RoundOffPolicy.NEAREST_WHOLE, "-0.10"),
        (RoundOffPolicy.DOWN, "-0.10"),
        (RoundOffPolicy.UP, "0.90"),
    ],
)
def test_configurable_round_off_policy(policy: RoundOffPolicy, expected: str) -> None:
    totals = SalesFinancialRulesEngine(round_off_policy=policy).calculate(
        [line(discount="10", cess="1")]
    )
    assert totals.round_off == Decimal(expected)


def test_payment_terms_calculate_due_date() -> None:
    engine = SalesFinancialRulesEngine()
    assert engine.due_date(date(2026, 7, 20), 30) == date(2026, 8, 19)
    with pytest.raises(SalesInvoiceValidationException):
        engine.due_date(date(2026, 7, 20), 10)


def test_due_date_cannot_precede_invoice_date() -> None:
    with pytest.raises(SalesInvoiceValidationException):
        SalesFinancialRulesEngine().validate_due_date(
            date(2026, 7, 20), date(2026, 7, 19)
        )


def test_currency_must_match_business_configuration() -> None:
    engine = SalesFinancialRulesEngine()
    assert engine.validate_currency(None, "INR") == "INR"
    with pytest.raises(SalesInvoiceValidationException):
        engine.validate_currency("USD", "INR")


def test_reconciliation_detects_tampered_totals() -> None:
    stored_line = SimpleNamespace(
        quantity=Decimal("1"),
        unit_price=Decimal("100"),
        discount=Decimal("0"),
        cgst_amount=Decimal("9"),
        sgst_amount=Decimal("9"),
        igst_amount=Decimal("0"),
        cess_amount=Decimal("0"),
    )
    invoice = SimpleNamespace(
        lines=[stored_line],
        subtotal=Decimal("100"),
        discount_amount=Decimal("0"),
        taxable_amount=Decimal("100"),
        tax_amount=Decimal("18"),
        round_off=Decimal("0"),
        total_amount=Decimal("119"),
        invoice_date=date(2026, 7, 20),
        due_date=date(2026, 7, 20),
    )
    with pytest.raises(SalesInvoiceValidationException) as error:
        SalesFinancialRulesEngine().reconcile(invoice)
    assert "total_amount" in error.value.details["fields"]


def test_reconciliation_accepts_consistent_invoice() -> None:
    stored_line = SimpleNamespace(
        quantity=Decimal("1"),
        unit_price=Decimal("100"),
        discount=Decimal("0"),
        cgst_amount=Decimal("9"),
        sgst_amount=Decimal("9"),
        igst_amount=Decimal("0"),
        cess_amount=Decimal("0"),
    )
    invoice = SimpleNamespace(
        lines=[stored_line],
        subtotal=Decimal("100"),
        discount_amount=Decimal("0"),
        taxable_amount=Decimal("100"),
        tax_amount=Decimal("18"),
        round_off=Decimal("0"),
        total_amount=Decimal("118"),
        invoice_date=date(2026, 7, 20),
        due_date=date(2026, 8, 19),
    )
    SalesFinancialRulesEngine().reconcile(invoice)
