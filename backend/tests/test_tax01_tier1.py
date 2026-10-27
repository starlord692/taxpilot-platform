"""TAX-01 Tier 1 Offline In-Memory Unit Test Suite.

Implements all 28 offline verification scenarios specified in Section 10.1 of TAX-01-SPECIFICATION.md:
- TAX-T1-01: B2B Intra-State standard (Karnataka)
- TAX-T1-02A to TAX-T1-02E: B2B Intra-State across all 5 domestic UTs (04, 26, 31, 35, 38)
- TAX-T1-03: B2B Inter-State standard (KA -> MH)
- TAX-T1-04: B2B Inter-State to Union Territory (attracts IGST, NOT UTGST)
- TAX-T1-05: B2B Service Inter-State (§ 12(2)(a))
- TAX-T1-06: B2C Goods with Shipping State (§ 10(1)(a) intra-state)
- TAX-T1-07: B2C Goods Inter-State with Shipping State (§ 10(1)(a) inter-state)
- TAX-T1-08: B2C Over-the-Counter Goods (§ 10(1)(c) supplier location)
- TAX-T1-09A: B2B Bill-to/Ship-to (§ 10(1)(b) cross-state delivery)
- TAX-T1-09B: B2B Bill-to/Ship-to (§ 10(1)(b) same-state delivery as buyer)
- TAX-T1-09C: B2B Bill-to/Ship-to (§ 10(1)(b) tripartite all in-state)
- TAX-T1-10: Direct Movement with Delivery State (§ 10(1)(a))
- TAX-T1-11: Contradictory POS Override Rejection (sales.invoice_contradictory_pos)
- TAX-T1-12: Odd-Cent Precision & Zero Drift
- TAX-T1-13: Multi-Line Mixed Rates
- TAX-T1-14: Zero-Rated / Exempt Supply
- TAX-T1-15: Unsupported SEZ Supply Rejection (sales.invoice_sez_unsupported)
- TAX-T1-16: Indeterminate Supplier State Rejection (sales.invoice_transaction_classification_indeterminate)
- TAX-T1-17: Invalid State Code Rejection (sales.invoice_invalid_state_code)
- TAX-T1-18: SEC-01 Cross-Tenant Isolation
- TAX-T1-19: UTGST Accounting Journal Balance (Canonical Account 2010)
- TAX-T1-20: Missing Shipping State on Out-of-State Goods (sales.invoice_shipping_state_required)
- TAX-T1-21: Service Line Ignores Shipping State (§ 12(2)(a))
- TAX-T1-22: Legacy State Code 25 Rejection (sales.invoice_legacy_state_code_obsolete)
- TAX-T1-23: Legacy Draft Missing POS Error (sales.invoice_place_of_supply_required)
- TAX-T1-24: Invoice and Journal Total Reconciliation (UTGST + CGST + Cess)
- TAX-T1-25: Offshore Code 97 Territory Rejection (sales.invoice_offshore_territory_unsupported)
- TAX-T1-26A to TAX-T1-26H: GSTIN Evidence Lifecycle & Bill-to/Ship-to Fail-Closed Checks
- TAX-T1-27: Multi-Line Mixed-Rate UTGST with Cess Ledger Balance
- TAX-T1-28: Historical Issued Invoice Read Compatibility & Snapshot Immutability

Execution: 100% offline, in-memory, zero PostgreSQL/Redis, zero external network.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Self

import pytest

from app.common.events import EventDispatcher
from app.common.exceptions import ValidationException
from app.modules.accounting.balances.models import AccountBalance
from app.modules.accounting.chart_of_accounts.models import Account, AccountType
from app.modules.accounting.journal.models import JournalEntry, JournalStatus
from app.modules.accounting.kernel import AccountingKernelService
from app.modules.accounting.ledger.models import GeneralLedgerEntry
from app.modules.gst.evidence import (
    BuyerRegistrationInvalidatedException,
    BuyerRegistrationStaleException,
    BuyerRegistrationUnverifiedException,
    FreshnessPolicy,
    FreshnessPolicyUndefinedException,
    GSTINEvidenceStatus,
    GSTINVerificationEvidence,
)
from app.modules.gst.jurisdictions import (
    InvalidStateCodeException,
    LegacyStateCodeObsoleteException,
    OffshoreTerritoryUnsupportedException,
    UTGST_JURISDICTIONS,
    is_utgst_jurisdiction,
    validate_state_code,
)
from app.modules.gst.services.gst_calculation_service import (
    GSTCalculationLineInput,
    GSTCalculationService,
    GSTSupplyType,
)
from app.modules.gst.services.pos_resolution_service import (
    TAX_DETERMINATION_ERROR_CATALOG,
    ConsigneeRequiredException,
    ContradictoryPOSException,
    DirectingPartyIndeterminateException,
    DirectionEvidenceType,
    DirectionTiming,
    DirectionTimingUnestablishedException,
    PlaceOfSupplyRequiredException,
    PlaceOfSupplyResolutionService,
    ResolvedTaxType,
    SEZUnsupportedException,
    ShippingStateRequiredException,
    SupplyCategory,
    SupplyResolutionContext,
    TransactionClassificationIndeterminateException,
)
from app.modules.sales.exceptions import SalesInvoiceNotFoundException
from app.modules.sales.models import (
    Customer,
    InvoiceStatus,
    SalesInvoice,
    SalesInvoiceLine,
)
from app.modules.sales.schemas import (
    InvoiceLineRequest,
    InvoiceResponse,
)
from app.modules.sales.services.invoice_service import SalesInvoiceService


# =============================================================================
# IN-MEMORY FIXTURES & FAKE REPOSITORIES
# =============================================================================


def build_valid_evidence(
    gstin: str,
    *,
    status: GSTINEvidenceStatus = GSTINEvidenceStatus.REGISTRATION_VERIFIED,
    age_days: int = 5,
    source: str = "SANDBOX_GST_VERIFIER",
) -> GSTINVerificationEvidence:
    """Build a valid or configured GSTINVerificationEvidence."""
    return GSTINVerificationEvidence(
        gstin=gstin,
        status=status,
        evidence_source=source,
        verified_at=datetime.now(UTC) - timedelta(days=age_days),
        internal_reviewer_identity="compliance_officer_01",
    )


def build_approved_policy(max_age_days: int = 30) -> FreshnessPolicy:
    """Build an approved tenant FreshnessPolicy."""
    return FreshnessPolicy(is_approved=True, max_age_days=max_age_days)


class FakeChartRepository:
    def __init__(self, accounts: list[Account]) -> None:
        self.accounts = {acc.account_code: acc for acc in accounts}

    async def get_account_by_code(
        self, *, business_id: uuid.UUID, account_code: str
    ) -> Account | None:
        _ = business_id
        return self.accounts.get(account_code)

    async def get_by_code(self, business_id: uuid.UUID, code: str) -> Account | None:
        _ = business_id
        return self.accounts.get(code)


class FakeJournalRepository:
    def __init__(self) -> None:
        self.journals: list[JournalEntry] = []

    async def add(self, entity: JournalEntry) -> JournalEntry:
        entity.id = entity.id or uuid.uuid4()
        for line in entity.lines:
            line.id = line.id or uuid.uuid4()
            line.journal_entry_id = entity.id
        self.journals.append(entity)
        return entity

    async def mark_posted(
        self,
        journal: JournalEntry,
        *,
        posting_date: date,
        period_id: uuid.UUID | None = None,
    ) -> JournalEntry:
        journal.status = JournalStatus.POSTED
        journal.posting_date = posting_date
        return journal


class FakeLedgerRepository:
    def __init__(self) -> None:
        self.entries: list[GeneralLedgerEntry] = []

    async def create_entries(
        self,
        entries: list[GeneralLedgerEntry],
    ) -> list[GeneralLedgerEntry]:
        for entry in entries:
            entry.id = entry.id or uuid.uuid4()
        self.entries.extend(entries)
        return entries

    async def exists_for_journal(self, journal_id: uuid.UUID) -> bool:
        return any(entry.journal_entry_id == journal_id for entry in self.entries)


class FakeBalanceRepository:
    def __init__(self) -> None:
        self.balances: dict[uuid.UUID, AccountBalance] = {}

    async def create_if_missing(
        self,
        *,
        business_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> AccountBalance:
        if account_id not in self.balances:
            self.balances[account_id] = AccountBalance(
                id=uuid.uuid4(),
                business_id=business_id,
                account_id=account_id,
                current_debit=Decimal("0.00"),
                current_credit=Decimal("0.00"),
                current_balance=Decimal("0.00"),
            )
        return self.balances[account_id]

    async def update_balance(
        self,
        balance: AccountBalance,
        *,
        debit_delta: Decimal,
        credit_delta: Decimal,
        last_posted_at: datetime,
    ) -> AccountBalance:
        _ = last_posted_at
        balance.current_debit += debit_delta
        balance.current_credit += credit_delta
        balance.current_balance = balance.current_debit - balance.current_credit
        return balance


class FakeInvoiceRepoForKernel:
    def __init__(self, invoice: SalesInvoice | None) -> None:
        self.invoice = invoice

    async def get_by_id(self, invoice_id: uuid.UUID) -> SalesInvoice | None:
        if self.invoice is None or self.invoice.id != invoice_id:
            return None
        return self.invoice


class FakeAccountingKernelUnitOfWork:
    def __init__(self, invoice: SalesInvoice) -> None:
        self.sales_invoices = FakeInvoiceRepoForKernel(invoice)
        b_id = invoice.business_id
        accounts = [
            Account(
                id=uuid.uuid4(),
                business_id=b_id,
                account_code="1020",
                account_name="Accounts Receivable",
                account_type_id=uuid.uuid4(),
                is_system=True,
                is_active=True,
            ),
            Account(
                id=uuid.uuid4(),
                business_id=b_id,
                account_code="4000",
                account_name="Sales Revenue",
                account_type_id=uuid.uuid4(),
                is_system=True,
                is_active=True,
            ),
            Account(
                id=uuid.uuid4(),
                business_id=b_id,
                account_code="2010",
                account_name="Output Tax Payable",
                account_type_id=uuid.uuid4(),
                is_system=True,
                is_active=True,
            ),
        ]
        self.chart_of_accounts = FakeChartRepository(accounts)
        self.journals = FakeJournalRepository()
        self.ledgers = FakeLedgerRepository()
        self.account_balances = FakeBalanceRepository()
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


# =============================================================================
# TIER 1 TESTS (TAX-T1-01 THROUGH TAX-T1-28)
# =============================================================================


def test_tax_t1_01_b2b_intra_state_standard():
    """TAX-T1-01: B2B Intra-State (LS=29 KA, Buyer=29 KA) -> CGST 9% + SGST 9%."""
    pos_service = PlaceOfSupplyResolutionService()
    calc_service = GSTCalculationService()

    evidence = build_valid_evidence("29AABCU9603R1ZM")
    policy = build_approved_policy()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="29AABCU9603R1ZM",
        buyer_evidence=evidence,
        freshness_policy=policy,
    )
    result = pos_service.resolve_supply(ctx)

    assert result.category == SupplyCategory.CAT_1_B2B_GOODS_MOVEMENT
    assert result.place_of_supply == "29"
    assert result.tax_type == ResolvedTaxType.INTRA_STATE_SGST
    assert result.is_intra_state is True
    assert result.is_utgst is False

    # Tax calculation: ₹1,000 @ 18%
    line = calc_service.calculate_line(
        GSTCalculationLineInput(
            description="Goods",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("1000.00"),
            tax_rate=Decimal("18.00"),
            supply_type=GSTSupplyType.INTRA_STATE,
            is_utgst=False,
        )
    )
    assert line.cgst_amount == Decimal("90.00")
    assert line.sgst_amount == Decimal("90.00")
    assert line.utgst_amount == Decimal("0.00")
    assert line.igst_amount == Decimal("0.00")
    assert line.line_total == Decimal("1180.00")


@pytest.mark.parametrize(
    ("ut_code", "ut_name"),
    [
        ("04", "Chandigarh"),
        ("26", "Dadra & Nagar Haveli and Daman & Diu"),
        ("31", "Lakshadweep"),
        ("35", "Andaman & Nicobar Islands"),
        ("38", "Ladakh"),
    ],
)
def test_tax_t1_02_b2b_intra_state_utgst_five_jurisdictions(ut_code: str, ut_name: str):
    """TAX-T1-02A to TAX-T1-02E: B2B Intra-State across all 5 domestic UTs -> CGST 9% + UTGST 9%."""
    pos_service = PlaceOfSupplyResolutionService()
    calc_service = GSTCalculationService()

    gstin = f"{ut_code}AABCU9603R1ZM"
    evidence = build_valid_evidence(gstin)
    policy = build_approved_policy()

    ctx = SupplyResolutionContext(
        supplier_state_code=ut_code,
        buyer_gstin=gstin,
        buyer_evidence=evidence,
        freshness_policy=policy,
    )
    result = pos_service.resolve_supply(ctx)

    assert result.place_of_supply == ut_code
    assert result.tax_type == ResolvedTaxType.INTRA_STATE_UTGST
    assert result.is_intra_state is True
    assert result.is_utgst is True

    # Tax calculation: ₹1,000 @ 18%
    line = calc_service.calculate_line(
        GSTCalculationLineInput(
            description=f"Supplies in {ut_name}",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("1000.00"),
            tax_rate=Decimal("18.00"),
            supply_type=GSTSupplyType.INTRA_STATE,
            is_utgst=True,
        )
    )
    assert line.cgst_amount == Decimal("90.00")
    assert line.sgst_amount == Decimal("0.00")
    assert line.utgst_amount == Decimal("90.00")
    assert line.igst_amount == Decimal("0.00")
    assert line.line_total == Decimal("1180.00")


def test_tax_t1_03_b2b_inter_state():
    """TAX-T1-03: B2B Inter-State (LS=29 KA, Buyer=27 MH) -> IGST 18%."""
    pos_service = PlaceOfSupplyResolutionService()
    calc_service = GSTCalculationService()

    evidence = build_valid_evidence("27AABCU9603R1ZM")
    policy = build_approved_policy()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="27AABCU9603R1ZM",
        buyer_evidence=evidence,
        freshness_policy=policy,
    )
    result = pos_service.resolve_supply(ctx)

    assert result.place_of_supply == "27"
    assert result.tax_type == ResolvedTaxType.INTER_STATE
    assert result.is_intra_state is False
    assert result.is_utgst is False

    line = calc_service.calculate_line(
        GSTCalculationLineInput(
            description="Inter-state goods",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("1000.00"),
            tax_rate=Decimal("18.00"),
            supply_type=GSTSupplyType.INTER_STATE,
        )
    )
    assert line.igst_amount == Decimal("180.00")
    assert line.cgst_amount == Decimal("0.00")
    assert line.sgst_amount == Decimal("0.00")
    assert line.utgst_amount == Decimal("0.00")


def test_tax_t1_04_b2b_inter_state_to_ut():
    """TAX-T1-04: Supply from State into UT (LS=29 KA -> Buyer=04 CH) attracts IGST, NOT UTGST."""
    pos_service = PlaceOfSupplyResolutionService()
    calc_service = GSTCalculationService()

    evidence = build_valid_evidence("04AABCU9603R1ZM")
    policy = build_approved_policy()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="04AABCU9603R1ZM",
        buyer_evidence=evidence,
        freshness_policy=policy,
    )
    result = pos_service.resolve_supply(ctx)

    assert result.place_of_supply == "04"
    assert result.tax_type == ResolvedTaxType.INTER_STATE
    assert result.is_intra_state is False
    assert result.is_utgst is False

    line = calc_service.calculate_line(
        GSTCalculationLineInput(
            description="Inter-state supply into UT",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("1000.00"),
            tax_rate=Decimal("18.00"),
            supply_type=GSTSupplyType.INTER_STATE,
            is_utgst=False,
        )
    )
    assert line.igst_amount == Decimal("180.00")
    assert line.utgst_amount == Decimal("0.00")


def test_tax_t1_05_b2b_service_inter_state():
    """TAX-T1-05: B2B Service Inter-State (§ 12(2)(a)) (LS=07 DL -> Buyer=06 HR)."""
    pos_service = PlaceOfSupplyResolutionService()
    calc_service = GSTCalculationService()

    evidence = build_valid_evidence("06AABCU9603R1ZM")
    policy = build_approved_policy()

    ctx = SupplyResolutionContext(
        supplier_state_code="07",
        buyer_gstin="06AABCU9603R1ZM",
        is_service=True,
        buyer_evidence=evidence,
        freshness_policy=policy,
    )
    result = pos_service.resolve_supply(ctx)

    assert result.category == SupplyCategory.CAT_2_B2B_SERVICES
    assert result.place_of_supply == "06"
    assert result.tax_type == ResolvedTaxType.INTER_STATE

    line = calc_service.calculate_line(
        GSTCalculationLineInput(
            description="Consulting Service",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("2000.00"),
            tax_rate=Decimal("18.00"),
            supply_type=GSTSupplyType.INTER_STATE,
        )
    )
    assert line.igst_amount == Decimal("360.00")


def test_tax_t1_06_b2c_goods_intra_state_with_shipping():
    """TAX-T1-06: B2C Goods with Shipping State (LS=29, shipping=29) -> Intra-State."""
    pos_service = PlaceOfSupplyResolutionService()
    calc_service = GSTCalculationService()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        shipping_state_code="29",
    )
    result = pos_service.resolve_supply(ctx)

    assert result.category == SupplyCategory.CAT_3_B2C_GOODS_DESTINATION
    assert result.place_of_supply == "29"
    assert result.is_intra_state is True

    line = calc_service.calculate_line(
        GSTCalculationLineInput(
            description="Consumer retail item",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("500.00"),
            tax_rate=Decimal("12.00"),
            supply_type=GSTSupplyType.INTRA_STATE,
        )
    )
    assert line.cgst_amount == Decimal("30.00")
    assert line.sgst_amount == Decimal("30.00")


def test_tax_t1_07_b2c_goods_inter_state_with_shipping():
    """TAX-T1-07: B2C Goods Inter-State with Shipping State (LS=29, shipping=33) -> IGST."""
    pos_service = PlaceOfSupplyResolutionService()
    calc_service = GSTCalculationService()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        shipping_state_code="33",
    )
    result = pos_service.resolve_supply(ctx)

    assert result.category == SupplyCategory.CAT_3_B2C_GOODS_DESTINATION
    assert result.place_of_supply == "33"
    assert result.is_intra_state is False

    line = calc_service.calculate_line(
        GSTCalculationLineInput(
            description="Interstate ecommerce item",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("500.00"),
            tax_rate=Decimal("12.00"),
            supply_type=GSTSupplyType.INTER_STATE,
        )
    )
    assert line.igst_amount == Decimal("60.00")


def test_tax_t1_08_b2c_otc_goods_supplier_location():
    """TAX-T1-08: B2C Over-the-Counter Goods (§ 10(1)(c)) -> POS defaults to store location (LS=27 MH)."""
    pos_service = PlaceOfSupplyResolutionService()
    calc_service = GSTCalculationService()

    ctx = SupplyResolutionContext(
        supplier_state_code="27",
        is_over_the_counter=True,
    )
    result = pos_service.resolve_supply(ctx)

    assert result.category == SupplyCategory.CAT_4_B2C_OTC
    assert result.place_of_supply == "27"
    assert result.is_intra_state is True

    line = calc_service.calculate_line(
        GSTCalculationLineInput(
            description="Store counter sale",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("100.00"),
            tax_rate=Decimal("5.00"),
            supply_type=GSTSupplyType.INTRA_STATE,
        )
    )
    assert line.cgst_amount == Decimal("2.50")
    assert line.sgst_amount == Decimal("2.50")


def test_tax_t1_09a_b2b_bill_to_ship_to_cross_state():
    """TAX-T1-09A: B2B Bill-to/Ship-to (§ 10(1)(b)) with cross-state movement (LS=29, Buyer=29, Delivery=27).

    Statutory Invariant: Deemed POS is the buyer's principal place of business (29).
    Since LS(29) == POS(29), the invoice between supplier and buyer is INTRA-STATE CGST + SGST.
    """
    pos_service = PlaceOfSupplyResolutionService()
    calc_service = GSTCalculationService()

    evidence = build_valid_evidence("29AABCU9603R1ZM")
    policy = build_approved_policy()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="29AABCU9603R1ZM",
        buyer_evidence=evidence,
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        direction_evidence_type=DirectionEvidenceType.PURCHASE_ORDER,
        shipping_consignee_name="Acme Logistics Hub MH",
        shipping_state_code="27",
    )
    result = pos_service.resolve_supply(ctx)

    assert result.category == SupplyCategory.CAT_5_B2B_BILL_TO_SHIP_TO
    assert result.place_of_supply == "29"
    assert result.is_intra_state is True

    line = calc_service.calculate_line(
        GSTCalculationLineInput(
            description="Tripartite goods cross-state",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("1000.00"),
            tax_rate=Decimal("18.00"),
            supply_type=GSTSupplyType.INTRA_STATE,
        )
    )
    assert line.cgst_amount == Decimal("90.00")
    assert line.sgst_amount == Decimal("90.00")


def test_tax_t1_09b_b2b_bill_to_ship_to_same_state_as_buyer():
    """TAX-T1-09B: B2B Bill-to/Ship-to (§ 10(1)(b)) where Delivery State matches Buyer State (LS=27 MH, Buyer=29 KA, Delivery=29 KA).

    Statutory Invariant: shipping_state_code == buyer_state is completely valid.
    LS(27) != POS(29) -> INTER-STATE IGST.
    """
    pos_service = PlaceOfSupplyResolutionService()
    calc_service = GSTCalculationService()

    evidence = build_valid_evidence("29AABCU9603R1ZM")
    policy = build_approved_policy()

    ctx = SupplyResolutionContext(
        supplier_state_code="27",
        buyer_gstin="29AABCU9603R1ZM",
        buyer_evidence=evidence,
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Buyer Local Depot KA",
        shipping_state_code="29",
    )
    result = pos_service.resolve_supply(ctx)

    assert result.category == SupplyCategory.CAT_5_B2B_BILL_TO_SHIP_TO
    assert result.place_of_supply == "29"
    assert result.is_intra_state is False

    line = calc_service.calculate_line(
        GSTCalculationLineInput(
            description="Interstate tripartite supply",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("1000.00"),
            tax_rate=Decimal("18.00"),
            supply_type=GSTSupplyType.INTER_STATE,
        )
    )
    assert line.igst_amount == Decimal("180.00")


def test_tax_t1_09c_b2b_bill_to_ship_to_all_in_state():
    """TAX-T1-09C: B2B Bill-to/Ship-to (§ 10(1)(b)) where LS=27 MH, Buyer=27 MH, Delivery=27 MH -> INTRA-STATE CGST+SGST."""
    pos_service = PlaceOfSupplyResolutionService()

    evidence = build_valid_evidence("27AABCU9603R1ZM")
    policy = build_approved_policy()

    ctx = SupplyResolutionContext(
        supplier_state_code="27",
        buyer_gstin="27AABCU9603R1ZM",
        buyer_evidence=evidence,
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.DURING_MOVEMENT,
        shipping_consignee_name="Third Party Client Hub MH",
        shipping_state_code="27",
    )
    result = pos_service.resolve_supply(ctx)

    assert result.category == SupplyCategory.CAT_5_B2B_BILL_TO_SHIP_TO
    assert result.place_of_supply == "27"
    assert result.is_intra_state is True


def test_tax_t1_10_direct_movement_delivery_state():
    """TAX-T1-10: Cat 1 Direct Movement (§ 10(1)(a)): LS=29, Buyer=27, Delivery=36, is_bill_to_ship_to=False -> POS=36."""
    pos_service = PlaceOfSupplyResolutionService()

    evidence = build_valid_evidence("27AABCU9603R1ZM")
    policy = build_approved_policy()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="27AABCU9603R1ZM",
        shipping_state_code="36",
        is_bill_to_ship_to=False,
        buyer_evidence=evidence,
        freshness_policy=policy,
    )
    result = pos_service.resolve_supply(ctx)

    assert result.category == SupplyCategory.CAT_1_B2B_GOODS_MOVEMENT
    assert result.place_of_supply == "36"
    assert result.is_intra_state is False


def test_tax_t1_11_contradictory_pos_override_rejection():
    """TAX-T1-11: Explicit POS override contradicting statutory determination fails closed."""
    pos_service = PlaceOfSupplyResolutionService()

    evidence = build_valid_evidence("29AABCU9603R1ZM")
    policy = build_approved_policy()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="29AABCU9603R1ZM",
        is_service=True,
        asserted_place_of_supply="27",  # Contradicts Sec 12(2)(a) recipient state (29)
        buyer_evidence=evidence,
        freshness_policy=policy,
    )
    with pytest.raises(ContradictoryPOSException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.error_code == "sales.invoice_contradictory_pos"


def test_tax_t1_12_odd_cent_precision_and_zero_drift():
    """TAX-T1-12: Odd-cent rounding ₹55.55 @ 5% total tax ₹2.78 -> CGST 1.39 + SGST 1.39 exactly."""
    calc_service = GSTCalculationService()

    line = calc_service.calculate_line(
        GSTCalculationLineInput(
            description="Odd cent item",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("55.55"),
            tax_rate=Decimal("5.00"),
            supply_type=GSTSupplyType.INTRA_STATE,
        )
    )
    assert line.tax_amount == Decimal("2.78")
    assert line.cgst_amount == Decimal("1.39")
    assert line.sgst_amount == Decimal("1.39")
    assert line.cgst_amount + line.sgst_amount == line.tax_amount


def test_tax_t1_13_multi_line_mixed_rates():
    """TAX-T1-13: Multi-Line mixed rates (Line 1 @ 18% ₹1,000, Line 2 @ 12% ₹500) -> IGST 240.00."""
    calc_service = GSTCalculationService()

    line1 = calc_service.calculate_line(
        GSTCalculationLineInput(
            description="Goods Line",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("1000.00"),
            tax_rate=Decimal("18.00"),
            supply_type=GSTSupplyType.INTER_STATE,
        )
    )
    line2 = calc_service.calculate_line(
        GSTCalculationLineInput(
            description="Service Line",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("500.00"),
            tax_rate=Decimal("12.00"),
            supply_type=GSTSupplyType.INTER_STATE,
        )
    )
    assert line1.taxable_value + line2.taxable_value == Decimal("1500.00")
    assert line1.igst_amount == Decimal("180.00")
    assert line2.igst_amount == Decimal("60.00")
    assert line1.tax_amount + line2.tax_amount == Decimal("240.00")
    assert line1.line_total + line2.line_total == Decimal("1740.00")


def test_tax_t1_14_zero_rated_exempt_item():
    """TAX-T1-14: Zero-rated supply (0.00% tax) -> All GST components strictly 0.00."""
    calc_service = GSTCalculationService()

    line = calc_service.calculate_line(
        GSTCalculationLineInput(
            description="Exempt essential goods",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("1000.00"),
            tax_rate=Decimal("0.00"),
            supply_type=GSTSupplyType.INTER_STATE,
        )
    )
    assert line.tax_amount == Decimal("0.00")
    assert line.cgst_amount == Decimal("0.00")
    assert line.sgst_amount == Decimal("0.00")
    assert line.utgst_amount == Decimal("0.00")
    assert line.igst_amount == Decimal("0.00")
    assert line.line_total == Decimal("1000.00")


def test_tax_t1_15_unsupported_sez_supply_rejection():
    """TAX-T1-15: Supplies to SEZ under Sec 7(5)(b) fail closed in Milestone 1."""
    pos_service = PlaceOfSupplyResolutionService()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        is_sez=True,
    )
    with pytest.raises(SEZUnsupportedException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.error_code == "sales.invoice_sez_unsupported"


@pytest.mark.asyncio
async def test_tax_t1_16_indeterminate_supplier_state_rejection():
    """TAX-T1-16: Business lacking active GST registration and address state fails closed."""

    class FakeBusiness:
        def __init__(self) -> None:
            self.id = uuid.uuid4()
            self.tax_profile = None
            self.address = None

    class FakeBusinessRepo:
        async def get_by_id(self, b_id: uuid.UUID) -> FakeBusiness:
            _ = b_id
            return FakeBusiness()

    class FakeUOW:
        def __init__(self) -> None:
            self.businesses = FakeBusinessRepo()

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            pass

    service = SalesInvoiceService(
        unit_of_work_factory=lambda: FakeUOW(),
        event_dispatcher=EventDispatcher(),
    )

    with pytest.raises(TransactionClassificationIndeterminateException) as exc_info:
        await service._resolve_supplier_state_code(FakeUOW(), uuid.uuid4())
    assert (
        exc_info.value.error_code
        == "sales.invoice_transaction_classification_indeterminate"
    )


def test_tax_t1_17_invalid_state_code_rejection():
    """TAX-T1-17: Invalid 2-digit GST state code (99) fails closed."""
    with pytest.raises(InvalidStateCodeException) as exc_info:
        validate_state_code("99")
    assert exc_info.value.error_code == "sales.invoice_invalid_state_code"


def test_tax_t1_18_sec01_cross_tenant_isolation():
    """TAX-T1-18: Querying invoice across tenant boundaries produces uniform isolation rejection."""
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    inv = SalesInvoice(
        id=uuid.uuid4(),
        business_id=tenant_b_id,
        invoice_number="INV-001",
        place_of_supply="27",
    )

    class TenantIsolatedRepo:
        def __init__(self, invoice: SalesInvoice) -> None:
            self.invoice = invoice

        def get_for_business(
            self, b_id: uuid.UUID, inv_id: uuid.UUID
        ) -> SalesInvoice | None:
            if self.invoice.business_id != b_id or self.invoice.id != inv_id:
                return None
            return self.invoice

    repo = TenantIsolatedRepo(inv)
    found = repo.get_for_business(tenant_a_id, inv.id)
    assert found is None


@pytest.mark.asyncio
async def test_tax_t1_19_utgst_accounting_journal_balance():
    """TAX-T1-19: UT Chandigarh invoice accounting balance: Debits == Credits (1020, 4000, 2010)."""
    b_id = uuid.uuid4()
    inv_id = uuid.uuid4()

    line = SalesInvoiceLine(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        description="Chandigarh Services",
        quantity=Decimal("1.00"),
        unit_price=Decimal("1000.00"),
        discount=Decimal("0.00"),
        tax_rate=Decimal("18.00"),
        cgst_amount=Decimal("90.00"),
        sgst_amount=Decimal("0.00"),
        utgst_amount=Decimal("90.00"),
        igst_amount=Decimal("0.00"),
        cess_amount=Decimal("0.00"),
        line_total=Decimal("1180.00"),
    )
    inv = SalesInvoice(
        id=inv_id,
        business_id=b_id,
        invoice_number="INV-CH-001",
        invoice_date=date.today(),
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("1000.00"),
        discount_amount=Decimal("0.00"),
        taxable_amount=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        place_of_supply="04",
        lines=[line],
    )

    uow = FakeAccountingKernelUnitOfWork(inv)
    kernel = AccountingKernelService(
        unit_of_work_factory=lambda: uow,
        event_dispatcher=EventDispatcher(),
    )

    journal = await kernel.record_sales_invoice(inv_id)
    assert journal is not None
    assert journal.status == JournalStatus.POSTED

    # Verify UTGST line exists in journal entries
    utgst_line = next(
        (l for l in journal.lines if "Output UTGST" in (l.description or "")),
        None,
    )
    assert utgst_line is not None
    assert utgst_line.credit == Decimal("90.00")
    assert utgst_line.debit == Decimal("0.00")

    # Mathematical Proof: Debits == Credits
    total_debits = sum((l.debit for l in journal.lines), Decimal("0.00"))
    total_credits = sum((l.credit for l in journal.lines), Decimal("0.00"))
    assert total_debits == Decimal("1180.00")
    assert total_credits == Decimal("1180.00")
    assert total_debits == total_credits


def test_tax_t1_20_missing_shipping_state_on_out_of_state_goods():
    """TAX-T1-20: Goods movement claimed to alternate state without shipping_state_code fails closed."""
    pos_service = PlaceOfSupplyResolutionService()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="29AABCU9603R1ZM",
        is_delivery_claimed_out_of_state=True,
        shipping_state_code=None,
    )
    with pytest.raises(ShippingStateRequiredException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.error_code == "sales.invoice_shipping_state_required"


def test_tax_t1_21_service_line_ignores_shipping_state():
    """TAX-T1-21: B2B Service line resolves POS to recipient location under § 12(2)(a), ignoring shipping_state_code."""
    pos_service = PlaceOfSupplyResolutionService()

    evidence = build_valid_evidence("29AABCU9603R1ZM")
    policy = build_approved_policy()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="29AABCU9603R1ZM",
        is_service=True,
        shipping_state_code="27",  # Shipping destination ignored for services
        buyer_evidence=evidence,
        freshness_policy=policy,
    )
    result = pos_service.resolve_supply(ctx)

    assert result.category == SupplyCategory.CAT_2_B2B_SERVICES
    assert result.place_of_supply == "29"
    assert result.is_intra_state is True


def test_tax_t1_22_legacy_state_code_25_rejection():
    """TAX-T1-22: Deprecated code 25 (Daman & Diu) is hard-rejected with explicit guidance to use 26."""
    with pytest.raises(LegacyStateCodeObsoleteException) as exc_info:
        validate_state_code("25")
    assert exc_info.value.error_code == "sales.invoice_legacy_state_code_obsolete"


def test_tax_t1_23_legacy_draft_missing_pos_error():
    """TAX-T1-23: Draft lacking POS and unresolvable from customer address facts fails closed."""
    pos_service = PlaceOfSupplyResolutionService()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin=None,
        shipping_address="Unresolvable Street Address Without Recognized State Code",
        shipping_state_code=None,
        is_service=False,
        is_over_the_counter=False,
    )
    with pytest.raises(PlaceOfSupplyRequiredException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.error_code == "sales.invoice_place_of_supply_required"


@pytest.mark.asyncio
async def test_tax_t1_24_invoice_and_journal_total_reconciliation():
    """TAX-T1-24: Multi-line mixed goods & services with UTGST, CGST, and Cess reconciles perfectly."""
    b_id = uuid.uuid4()
    inv_id = uuid.uuid4()

    line1 = SalesInvoiceLine(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        description="Item 1 @ 18% in UT",
        quantity=Decimal("1.00"),
        unit_price=Decimal("1000.00"),
        discount=Decimal("0.00"),
        tax_rate=Decimal("18.00"),
        cgst_amount=Decimal("90.00"),
        sgst_amount=Decimal("0.00"),
        utgst_amount=Decimal("90.00"),
        igst_amount=Decimal("0.00"),
        cess_amount=Decimal("0.00"),
        line_total=Decimal("1180.00"),
    )
    line2 = SalesInvoiceLine(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        description="Item 2 @ 12% + Cess in UT",
        quantity=Decimal("1.00"),
        unit_price=Decimal("1000.00"),
        discount=Decimal("0.00"),
        tax_rate=Decimal("12.00"),
        cgst_amount=Decimal("60.00"),
        sgst_amount=Decimal("0.00"),
        utgst_amount=Decimal("60.00"),
        igst_amount=Decimal("0.00"),
        cess_amount=Decimal("50.00"),
        line_total=Decimal("1170.00"),
    )
    inv = SalesInvoice(
        id=inv_id,
        business_id=b_id,
        invoice_number="INV-CH-002",
        invoice_date=date.today(),
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("2000.00"),
        discount_amount=Decimal("0.00"),
        taxable_amount=Decimal("2000.00"),
        tax_amount=Decimal("350.00"),
        total_amount=Decimal("2350.00"),
        place_of_supply="04",
        lines=[line1, line2],
    )

    uow = FakeAccountingKernelUnitOfWork(inv)
    kernel = AccountingKernelService(
        unit_of_work_factory=lambda: uow,
        event_dispatcher=EventDispatcher(),
    )

    journal = await kernel.record_sales_invoice(inv_id)
    assert journal is not None

    total_debits = sum((l.debit for l in journal.lines), Decimal("0.00"))
    total_credits = sum((l.credit for l in journal.lines), Decimal("0.00"))
    assert total_debits == Decimal("2350.00")
    assert total_credits == Decimal("2350.00")
    assert total_debits == total_credits


def test_tax_t1_25_offshore_code_97_rejection():
    """TAX-T1-25: Code 97 (Other Territory) offshore territorial operations fail closed."""
    with pytest.raises(OffshoreTerritoryUnsupportedException) as exc_info:
        validate_state_code("97")
    assert exc_info.value.error_code == "sales.invoice_offshore_territory_unsupported"


def test_tax_t1_26a_format_valid_unverified_gstin_fails_closed():
    """TAX-T1-26A: Bill-to/Ship-to with FORMAT_VALIDATED_UNVERIFIED buyer fails closed."""
    pos_service = PlaceOfSupplyResolutionService()

    evidence = build_valid_evidence(
        "29AABCU9603R1ZM", status=GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED
    )
    policy = build_approved_policy()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="29AABCU9603R1ZM",
        buyer_evidence=evidence,
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Acme Hub",
        shipping_state_code="27",
    )
    with pytest.raises(BuyerRegistrationUnverifiedException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.error_code == "sales.invoice_buyer_registration_unconfirmed"


def test_tax_t1_26b_missing_or_unknown_direction_timing_fails_closed():
    """TAX-T1-26B: Bill-to/Ship-to with missing or unknown direction timing fails closed."""
    pos_service = PlaceOfSupplyResolutionService()

    evidence = build_valid_evidence("29AABCU9603R1ZM")
    policy = build_approved_policy()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="29AABCU9603R1ZM",
        buyer_evidence=evidence,
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=None,  # Missing direction timing
        shipping_consignee_name="Acme Hub",
        shipping_state_code="27",
    )
    with pytest.raises(DirectionTimingUnestablishedException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.error_code == "sales.invoice_direction_timing_unestablished"


def test_tax_t1_26c_missing_consignee_on_bill_to_ship_to_fails_closed():
    """TAX-T1-26C: Bill-to/Ship-to without shipping_consignee_name fails closed."""
    pos_service = PlaceOfSupplyResolutionService()

    evidence = build_valid_evidence("29AABCU9603R1ZM")
    policy = build_approved_policy()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="29AABCU9603R1ZM",
        buyer_evidence=evidence,
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name=None,  # Missing consignee
        shipping_state_code="27",
    )
    with pytest.raises(ConsigneeRequiredException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.error_code == "sales.invoice_consignee_required"


def test_tax_t1_26d_missing_shipping_state_on_bill_to_ship_to_fails_closed():
    """TAX-T1-26D: Bill-to/Ship-to without shipping_state_code fails closed."""
    pos_service = PlaceOfSupplyResolutionService()

    evidence = build_valid_evidence("29AABCU9603R1ZM")
    policy = build_approved_policy()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="29AABCU9603R1ZM",
        buyer_evidence=evidence,
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Acme Hub",
        shipping_state_code=None,  # Missing destination state
    )
    with pytest.raises(ShippingStateRequiredException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.error_code == "sales.invoice_shipping_state_required"


def test_tax_t1_26e_freshness_policy_undefined_fails_closed():
    """TAX-T1-26E: Freshness policy undefined (default lock) blocks invoice issuance."""
    pos_service = PlaceOfSupplyResolutionService()

    evidence = build_valid_evidence("29AABCU9603R1ZM")
    unapproved_policy = FreshnessPolicy(is_approved=False, max_age_days=30)

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="29AABCU9603R1ZM",
        buyer_evidence=evidence,
        freshness_policy=unapproved_policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Acme Hub",
        shipping_state_code="27",
    )
    with pytest.raises(FreshnessPolicyUndefinedException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.error_code == "sales.invoice_freshness_policy_undefined"


def test_tax_t1_26f_stale_verification_evidence_fails_closed():
    """TAX-T1-26F: Verification evidence older than max_age_days fails closed."""
    pos_service = PlaceOfSupplyResolutionService()

    stale_evidence = build_valid_evidence("29AABCU9603R1ZM", age_days=45)
    policy = build_approved_policy(max_age_days=30)

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="29AABCU9603R1ZM",
        buyer_evidence=stale_evidence,
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Acme Hub",
        shipping_state_code="27",
    )
    with pytest.raises(BuyerRegistrationStaleException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.error_code == "sales.invoice_buyer_registration_stale"


def test_tax_t1_26g_invalidated_verification_evidence_fails_closed():
    """TAX-T1-26G: Invalidated buyer registration evidence fails closed."""
    pos_service = PlaceOfSupplyResolutionService()

    invalidated_evidence = build_valid_evidence(
        "29AABCU9603R1ZM", status=GSTINEvidenceStatus.INVALIDATED
    )
    policy = build_approved_policy()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="29AABCU9603R1ZM",
        buyer_evidence=invalidated_evidence,
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Acme Hub",
        shipping_state_code="27",
    )
    with pytest.raises(BuyerRegistrationInvalidatedException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.error_code == "sales.invoice_buyer_registration_invalidated"


def test_tax_t1_26h_agency_direction_fails_closed():
    """TAX-T1-26H: Agency direction (directing_party_is_billed_buyer=False) fails closed in Milestone 1."""
    pos_service = PlaceOfSupplyResolutionService()

    evidence = build_valid_evidence("29AABCU9603R1ZM")
    policy = build_approved_policy()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="29AABCU9603R1ZM",
        buyer_evidence=evidence,
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=False,  # Intermediary / Agent direction
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Acme Hub",
        shipping_state_code="27",
    )
    with pytest.raises(DirectingPartyIndeterminateException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.error_code == "sales.invoice_directing_party_indeterminate"


def test_tax_t1_26i_omitted_directing_party_fails_closed():
    """TAX-T1-26I: Omitted directing party (directing_party_is_billed_buyer=None) fails closed as indeterminate."""
    pos_service = PlaceOfSupplyResolutionService()

    evidence = build_valid_evidence("29AABCU9603R1ZM")
    policy = build_approved_policy()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="29AABCU9603R1ZM",
        buyer_evidence=evidence,
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        # directing_party_is_billed_buyer omitted (defaults to None)
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Acme Hub",
        shipping_state_code="27",
    )
    with pytest.raises(DirectingPartyIndeterminateException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.error_code == "sales.invoice_directing_party_indeterminate"


def test_tax_t1_26j_contradictory_directing_party_on_non_bill_to_ship_to_fails_closed():
    """TAX-T1-26J: Asserting directing party on non-bill-to/ship-to supply fails closed."""
    pos_service = PlaceOfSupplyResolutionService()

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="27AABCB1234F1Z1",
        is_bill_to_ship_to=False,
        directing_party_is_billed_buyer=True,  # Contradictory assertion
    )
    with pytest.raises(DirectingPartyIndeterminateException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.error_code == "sales.invoice_directing_party_indeterminate"


@pytest.mark.asyncio
async def test_tax_t1_27_multi_line_mixed_rate_utgst_with_cess_ledger_balance():
    """TAX-T1-27: Multi-Line mixed-rate UTGST with Cess (Lines @ 5% + 18% + Cess in UT 04) ledger balance."""
    b_id = uuid.uuid4()
    inv_id = uuid.uuid4()

    line1 = SalesInvoiceLine(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        description="UT 5% Line",
        quantity=Decimal("1.00"),
        unit_price=Decimal("1000.00"),
        discount=Decimal("0.00"),
        tax_rate=Decimal("5.00"),
        cgst_amount=Decimal("25.00"),
        sgst_amount=Decimal("0.00"),
        utgst_amount=Decimal("25.00"),
        igst_amount=Decimal("0.00"),
        cess_amount=Decimal("0.00"),
        line_total=Decimal("1050.00"),
    )
    line2 = SalesInvoiceLine(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        description="UT 18% Line + Cess",
        quantity=Decimal("1.00"),
        unit_price=Decimal("2000.00"),
        discount=Decimal("0.00"),
        tax_rate=Decimal("18.00"),
        cgst_amount=Decimal("180.00"),
        sgst_amount=Decimal("0.00"),
        utgst_amount=Decimal("180.00"),
        igst_amount=Decimal("0.00"),
        cess_amount=Decimal("100.00"),
        line_total=Decimal("2460.00"),
    )
    inv = SalesInvoice(
        id=inv_id,
        business_id=b_id,
        invoice_number="INV-CH-MIXED",
        invoice_date=date.today(),
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("3000.00"),
        discount_amount=Decimal("0.00"),
        taxable_amount=Decimal("3000.00"),
        tax_amount=Decimal("510.00"),
        total_amount=Decimal("3510.00"),
        place_of_supply="04",
        lines=[line1, line2],
    )

    uow = FakeAccountingKernelUnitOfWork(inv)
    kernel = AccountingKernelService(
        unit_of_work_factory=lambda: uow,
        event_dispatcher=EventDispatcher(),
    )

    journal = await kernel.record_sales_invoice(inv_id)
    assert journal is not None

    total_debits = sum((l.debit for l in journal.lines), Decimal("0.00"))
    total_credits = sum((l.credit for l in journal.lines), Decimal("0.00"))
    assert total_debits == Decimal("3510.00")
    assert total_credits == Decimal("3510.00")
    assert total_debits == total_credits


def test_tax_t1_28_historical_invoice_read_compatibility_and_snapshot_immutability():
    """TAX-T1-28: Historical invoice created pre-TAX-01 serializes cleanly with place_of_supply=None and utgst_amount=0.00."""
    inv_id = uuid.uuid4()
    inv = SalesInvoice(
        id=inv_id,
        business_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        invoice_number="INV-HISTORICAL-001",
        invoice_date=date(2025, 1, 1),
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("1000.00"),
        discount_amount=Decimal("0.00"),
        taxable_amount=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        place_of_supply=None,  # Pre-TAX-01 column null value
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=inv_id,
                description="Historical Item",
                quantity=Decimal("1.00"),
                unit_price=Decimal("1000.00"),
                discount=Decimal("0.00"),
                tax_rate=Decimal("18.00"),
                line_total=Decimal("1180.00"),
                cgst_amount=Decimal("90.00"),
                sgst_amount=Decimal("90.00"),
                utgst_amount=Decimal("0.00"),  # Pre-TAX-01 default
                igst_amount=Decimal("0.00"),
            )
        ],
    )

    response = InvoiceResponse.model_validate(inv)
    assert response.place_of_supply is None
    assert len(response.lines) == 1
    assert response.lines[0].utgst_amount == Decimal("0.00")
    assert response.total_amount == Decimal("1180.00")


def test_tax_t1_29_error_catalog_completeness() -> None:
    """TAX-T1-29: Error catalog contains all 12 canonical codes (HTTP 422)."""
    expected_status = 422
    expected_codes = {
        "sales.invoice_directing_party_indeterminate",
        "sales.invoice_freshness_policy_undefined",
        "sales.invoice_buyer_registration_unconfirmed",
        "sales.invoice_buyer_registration_stale",
        "sales.invoice_buyer_registration_invalidated",
        "sales.invoice_direction_timing_unestablished",
        "sales.invoice_consignee_required",
        "sales.invoice_shipping_state_required",
        "sales.invoice_place_of_supply_required",
        "sales.invoice_contradictory_pos",
        "sales.invoice_offshore_territory_unsupported",
        "sales.invoice_legacy_state_code_obsolete",
    }
    assert expected_codes.issubset(set(TAX_DETERMINATION_ERROR_CATALOG.keys()))

    for code in expected_codes:
        contract = TAX_DETERMINATION_ERROR_CATALOG[code]
        assert contract.error_code == code
        assert contract.http_status == expected_status
        assert len(contract.failure_condition) > 0
        assert len(contract.remediation_guidance) > 0
        assert issubclass(contract.exception_class, ValidationException)


def test_tax_t1_30_structured_audit_logging_on_resolution(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """TAX-T1-30: POS determination emits tax_determination_resolved audit log."""
    pos_service = PlaceOfSupplyResolutionService()
    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="29ABCDE1234F1Z5",
        buyer_state_code="29",
    )
    with caplog.at_level("INFO"):
        result = pos_service.resolve_supply(ctx)

    assert result.place_of_supply == "29"
    assert result.tax_type == ResolvedTaxType.INTRA_STATE_SGST

    matching_records = [
        rec for rec in caplog.records if rec.message == "tax_determination_resolved"
    ]
    assert len(matching_records) == 1
    rec = matching_records[0]
    assert rec.supplier_state == "29"
    assert rec.place_of_supply == "29"
    assert rec.category == SupplyCategory.CAT_1_B2B_GOODS_MOVEMENT.value
    assert rec.tax_type == ResolvedTaxType.INTRA_STATE_SGST.value
    assert rec.is_intra_state is True
    assert rec.is_utgst is False
    assert "Section 10(1)(a)" in rec.derivation_basis


def test_tax_t1_31_structured_audit_logging_on_rejection(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """TAX-T1-31: Validation rejection emits tax_determination_rejected warning log."""
    pos_service = PlaceOfSupplyResolutionService()
    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        asserted_place_of_supply="27",
        buyer_gstin="29ABCDE1234F1Z5",
        buyer_state_code="29",
    )
    with caplog.at_level("WARNING"), pytest.raises(ContradictoryPOSException):
        pos_service.resolve_supply(ctx)

    matching_records = [
        rec for rec in caplog.records if "tax_determination_rejected" in rec.message
    ]
    assert len(matching_records) == 1
    rec = matching_records[0]
    assert rec.reason == "sales.invoice_contradictory_pos"
    assert rec.supplier_state == "29"
    assert "asserted" in rec.details
    assert rec.details["asserted"] == "27"
    assert rec.details["resolved"] == "29"

