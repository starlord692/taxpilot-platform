"""GST Compliance Engine."""

import csv
import io
import re
import uuid
from calendar import monthrange
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel

from app.common.events import EventDispatcher
from app.modules.expenses.models import Expense, ExpenseStatus
from app.modules.gst.compliance.models import GSTFilingFrequency
from app.modules.gst.compliance.schemas import (
    GSTAmountSummary,
    GSTAuditIssue,
    GSTAuditReportResponse,
    GSTR1Report,
    GSTR3BReport,
    GSTReportPeriod,
    GSTReportRequest,
    GSTRReconciliationDiscrepancy,
    GSTRReconciliationReport,
    GSTRReconciliationStatus,
    GSTSummaryReport,
    HSNReportLine,
    ITCReport,
    ReconciliationDataSource,
)
from app.modules.gst.events import (
    GSTAuditCompletedEvent,
    GSTReconciliationCompletedEvent,
    GSTReturnGeneratedEvent,
)
from app.modules.gst.evidence import (
    APPROVED_TESTBED_VERIFICATION_SOURCES,
    AUTHORIZED_PRODUCTION_VERIFICATION_SOURCES,
)
from app.modules.gst.exceptions import (
    GSTComparisonInputValidationException,
    GSTInvalidPeriodException,
)
from app.modules.gst.services.gst_calculation_service import GSTSupplyType
from app.modules.purchases.models import PurchaseInvoice, PurchaseStatus
from app.modules.sales.models import InvoiceStatus, SalesInvoice

ZERO_AMOUNT = Decimal("0.00")
FINANCIAL_YEAR_START_MONTH = 4
DECEMBER = 12
MONTHS_PER_QUARTER = 3


class SupplyCategory(StrEnum):
    """Statutory outward supply categories for GST returns."""

    B2B = "b2b"
    B2C = "b2c"
    EXPORTS = "exports"
    NIL_RATED = "nil_rated"
    EXEMPT = "exempt"


POSTED_SALES_STATUSES = {
    InvoiceStatus.ISSUED,
    InvoiceStatus.PARTIALLY_PAID,
    InvoiceStatus.PAID,
}
POSTED_PURCHASE_STATUSES = {
    PurchaseStatus.APPROVED,
    PurchaseStatus.RECEIVED,
    PurchaseStatus.PAID,
}
POSTED_EXPENSE_STATUSES = {
    ExpenseStatus.APPROVED,
    ExpenseStatus.PAID,
}


class GSTComplianceReadRepository(Protocol):
    """Repository behavior required by the GST Compliance Engine."""

    async def list_sales(
        self,
        *,
        business_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> list[SalesInvoice]:
        """Return sales invoices for a period."""
        ...

    async def list_purchases(
        self,
        *,
        business_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> list[PurchaseInvoice]:
        """Return purchase invoices for a period."""
        ...

    async def list_expenses(
        self,
        *,
        business_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> list[Expense]:
        """Return expenses for a period."""
        ...


class GSTComplianceUnitOfWork(Protocol):
    """Unit of Work contract for GST compliance reporting."""

    gst_compliance: GSTComplianceReadRepository

    async def __aenter__(self) -> "GSTComplianceUnitOfWork":
        """Enter transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit read transaction."""
        ...


UnitOfWorkFactory = Callable[[], GSTComplianceUnitOfWork]


class GSTComplianceService:
    """Generate statutory GST reports from posted source data."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
    ) -> None:
        """Initialize dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher

    async def generate_gstr1(self, request: GSTReportRequest) -> GSTR1Report:
        """Generate GSTR-1 from posted sales data."""
        period, sales, _purchases, _expenses = await self._load_sources(request)
        summaries = self._classify_and_summarize_sales(sales)

        report = GSTR1Report(
            period=period,
            b2b=summaries[SupplyCategory.B2B],
            b2c=summaries[SupplyCategory.B2C],
            exports=summaries[SupplyCategory.EXPORTS],
            credit_notes=GSTAmountSummary(),
            debit_notes=GSTAmountSummary(),
            nil_rated=summaries[SupplyCategory.NIL_RATED],
            exempt=summaries[SupplyCategory.EXEMPT],
            hsn_summary=self._hsn_summary(sales),
            document_summary={"sales_invoices": len(sales)},
        )
        await self._publish_return(period, "gstr1")
        return report

    async def generate_gstr3b(self, request: GSTReportRequest) -> GSTR3BReport:
        """Generate GSTR-3B from posted sales, purchases, and expenses."""
        period, sales, purchases, expenses = await self._load_sources(request)
        summaries = self._classify_and_summarize_sales(sales)
        b2b = summaries[SupplyCategory.B2B]
        b2c = summaries[SupplyCategory.B2C]
        exports = summaries[SupplyCategory.EXPORTS]
        nil_rated = summaries[SupplyCategory.NIL_RATED]
        exempt = summaries[SupplyCategory.EXEMPT]

        outward = self._rounded_summary(
            GSTAmountSummary(
                taxable_value=b2b.taxable_value + b2c.taxable_value,
                cgst_amount=b2b.cgst_amount + b2c.cgst_amount,
                sgst_amount=b2b.sgst_amount + b2c.sgst_amount,
                igst_amount=b2b.igst_amount + b2c.igst_amount,
                utgst_amount=b2b.utgst_amount + b2c.utgst_amount,
                cess_amount=b2b.cess_amount + b2c.cess_amount,
                tax_amount=b2b.tax_amount + b2c.tax_amount,
                total_amount=b2b.total_amount + b2c.total_amount,
            )
        )
        exempt_supplies = self._rounded_summary(
            GSTAmountSummary(
                taxable_value=nil_rated.taxable_value + exempt.taxable_value,
                cgst_amount=ZERO_AMOUNT,
                sgst_amount=ZERO_AMOUNT,
                igst_amount=ZERO_AMOUNT,
                utgst_amount=ZERO_AMOUNT,
                cess_amount=ZERO_AMOUNT,
                tax_amount=ZERO_AMOUNT,
                total_amount=nil_rated.total_amount + exempt.total_amount,
            )
        )
        inward = self._summarize_documents([*purchases, *expenses])
        itc = self._input_tax_credit(purchases, expenses)
        liability = GSTAmountSummary(
            taxable_value=outward.taxable_value,
            cgst_amount=outward.cgst_amount,
            sgst_amount=outward.sgst_amount,
            igst_amount=outward.igst_amount,
            utgst_amount=outward.utgst_amount,
            cess_amount=outward.cess_amount,
            tax_amount=outward.tax_amount,
            total_amount=outward.tax_amount,
        )
        report = GSTR3BReport(
            period=period,
            outward_taxable_supplies=outward,
            zero_rated_supplies=exports,
            exempt_supplies=exempt_supplies,
            inward_supplies=inward,
            reverse_charge=GSTAmountSummary(),
            input_tax_credit=itc,
            tax_liability=liability,
            net_gst_payable=max(liability.tax_amount - itc.tax_amount, ZERO_AMOUNT),
        )
        await self._publish_return(period, "gstr3b")
        return report

    async def generate_itc_report(self, request: GSTReportRequest) -> ITCReport:
        """Generate input tax credit report."""
        period, _sales, purchases, expenses = await self._load_sources(request)
        eligible = self._input_tax_credit(purchases, expenses)
        report = ITCReport(
            period=period,
            eligible_itc=eligible,
            blocked_itc=GSTAmountSummary(),
            rcm_itc=GSTAmountSummary(),
            pending_itc=GSTAmountSummary(),
        )
        await self._publish_return(period, "itc")
        return report

    async def generate_reconciliation(
        self,
        request: GSTReportRequest,
        *,
        gstr3b_liability_override: GSTAmountSummary | None = None,
        gstr3b_itc_override: GSTAmountSummary | None = None,
        comparison_source: ReconciliationDataSource | str | None = None,
        is_portal_verified: bool = False,
    ) -> GSTRReconciliationReport:
        """Generate GSTR-1 vs GSTR-3B and ITC Reconciliation Report.

        Reconciles GSTR-1 outward liability vs GSTR-3B, and inward books ITC
        vs GSTR-3B. Internal variance alerts are non-statutory advisory
        heuristics, not official GST portal determinations under Rule 88C/88D.
        """
        period, sales, purchases, expenses = await self._load_sources(request)
        summaries = self._classify_and_summarize_sales(sales)
        b2b = summaries[SupplyCategory.B2B]
        b2c = summaries[SupplyCategory.B2C]
        exports = summaries[SupplyCategory.EXPORTS]
        nil_rated = summaries[SupplyCategory.NIL_RATED]
        exempt = summaries[SupplyCategory.EXEMPT]

        gstr1_outward = self._rounded_summary(
            GSTAmountSummary(
                taxable_value=b2b.taxable_value + b2c.taxable_value,
                cgst_amount=b2b.cgst_amount + b2c.cgst_amount,
                sgst_amount=b2b.sgst_amount + b2c.sgst_amount,
                igst_amount=b2b.igst_amount + b2c.igst_amount,
                utgst_amount=b2b.utgst_amount + b2c.utgst_amount,
                cess_amount=b2b.cess_amount + b2c.cess_amount,
                tax_amount=b2b.tax_amount + b2c.tax_amount,
                total_amount=b2b.total_amount + b2c.total_amount,
            )
        )
        gstr1_total_turnover = self._money(
            b2b.taxable_value
            + b2c.taxable_value
            + exports.taxable_value
            + nil_rated.taxable_value
            + exempt.taxable_value
        )
        itc_books = self._input_tax_credit(purchases, expenses)

        has_liability_override = gstr3b_liability_override is not None
        has_itc_override = gstr3b_itc_override is not None

        resolved_source, resolved_portal_verified = (
            self._validate_comparison_provenance(
                comparison_source=comparison_source,
                is_portal_verified=is_portal_verified,
                has_overrides=(has_liability_override or has_itc_override),
            )
        )

        if gstr3b_liability_override is not None:
            self._validate_override_amounts(gstr3b_liability_override, "liability")
        if gstr3b_itc_override is not None:
            self._validate_override_amounts(gstr3b_itc_override, "itc")

        if not has_liability_override and not has_itc_override:
            report = self._build_non_comparable_report(
                period,
                gstr1_outward,
                itc_books,
                gstr1_total_turnover,
            )
            await self._event_dispatcher.dispatch(
                GSTReconciliationCompletedEvent.from_report(report)
            )
            return report

        non_taxable_turnover = (
            exports.taxable_value + nil_rated.taxable_value + exempt.taxable_value
        )
        (
            is_outward_compared,
            gstr3b_outward,
            outward_discrepancy,
            gstr3b_total_turnover,
            turnover_discrepancy,
            is_outward_matched,
            drc01b_risk,
        ) = self._reconcile_outward(
            gstr1_outward=gstr1_outward,
            gstr1_total_turnover=gstr1_total_turnover,
            override=gstr3b_liability_override,
            non_taxable_turnover=non_taxable_turnover,
        )

        (
            is_itc_compared,
            itc_gstr3b,
            itc_discrepancy,
            is_itc_matched,
            drc01c_risk,
        ) = self._reconcile_itc(
            itc_books=itc_books,
            override=gstr3b_itc_override,
        )

        variance_reasons = self._collect_variance_reasons(
            has_liability_override=has_liability_override,
            has_itc_override=has_itc_override,
            is_outward_matched=is_outward_matched,
            is_itc_matched=is_itc_matched,
            outward_discrepancy=outward_discrepancy,
            itc_discrepancy=itc_discrepancy,
            turnover_discrepancy=turnover_discrepancy,
        )

        reconciliation_status, requires_policy_approval = (
            self._determine_reconciliation_status(
                drc01b_risk=drc01b_risk,
                drc01c_risk=drc01c_risk,
                is_outward_compared=is_outward_compared,
                is_itc_compared=is_itc_compared,
                is_outward_matched=is_outward_matched,
                is_itc_matched=is_itc_matched,
            )
        )

        report = GSTRReconciliationReport(
            period=period,
            status=reconciliation_status,
            comparison_source=resolved_source,
            is_portal_verified=resolved_portal_verified,
            is_comparison_performed=True,
            is_outward_compared=is_outward_compared,
            is_itc_compared=is_itc_compared,
            is_outward_matched=is_outward_matched,
            is_itc_matched=is_itc_matched,
            requires_policy_approval=requires_policy_approval,
            statutory_determination_claim=False,
            drc01b_risk=drc01b_risk,
            drc01c_risk=drc01c_risk,
            variance_reasons=variance_reasons,
            gstr1_outward=gstr1_outward,
            gstr3b_outward=gstr3b_outward,
            outward_discrepancy=outward_discrepancy,
            itc_books=itc_books,
            itc_gstr3b=itc_gstr3b,
            itc_discrepancy=itc_discrepancy,
            gstr1_total_turnover=gstr1_total_turnover,
            gstr3b_total_turnover=gstr3b_total_turnover,
            turnover_discrepancy=turnover_discrepancy,
        )
        await self._event_dispatcher.dispatch(
            GSTReconciliationCompletedEvent.from_report(report)
        )
        return report

    def _validate_comparison_provenance(
        self,
        *,
        comparison_source: ReconciliationDataSource | str | None,
        is_portal_verified: bool,
        has_overrides: bool,
    ) -> tuple[ReconciliationDataSource, bool]:
        """Validate comparison provenance and server-authoritative evidence."""
        if is_portal_verified:
            raise GSTComparisonInputValidationException(
                "Government portal verification requires authorized server-side "
                "provider evidence, which is unavailable in offline scope."
            )
        source_str = (
            comparison_source.value
            if isinstance(comparison_source, ReconciliationDataSource)
            else str(comparison_source).strip().lower()
            if comparison_source is not None
            else None
        )
        if source_str in (
            "government_portal",
            "portal",
            ReconciliationDataSource.GOVERNMENT_PORTAL.value,
        ) or (
            source_str is not None
            and any(
                source_str == p.lower()
                for p in AUTHORIZED_PRODUCTION_VERIFICATION_SOURCES
            )
        ):
            raise GSTComparisonInputValidationException(
                "Government portal comparison source cannot be selected without "
                "authorized server-side provider evidence."
            )
        if source_str in ("mock", "sandbox", "testbed") or (
            source_str is not None
            and any(
                source_str == s.lower()
                for s in APPROVED_TESTBED_VERIFICATION_SOURCES
            )
        ):
            raise GSTComparisonInputValidationException(
                "Testbed or mock sources cannot satisfy government portal "
                "verification or comparison provenance."
            )
        if source_str is not None and source_str not in (
            ReconciliationDataSource.UNPROVIDED.value,
            ReconciliationDataSource.USER_SUPPLIED.value,
        ):
            raise GSTComparisonInputValidationException(
                f"Unsupported comparison source: '{source_str}'."
            )
        if not has_overrides:
            return ReconciliationDataSource.UNPROVIDED, False
        return ReconciliationDataSource.USER_SUPPLIED, False

    def _build_non_comparable_report(
        self,
        period: GSTReportPeriod,
        gstr1_outward: GSTAmountSummary,
        itc_books: GSTAmountSummary,
        gstr1_total_turnover: Decimal,
    ) -> GSTRReconciliationReport:
        """Build fail-closed report when return comparison data is unprovided."""
        return GSTRReconciliationReport(
            period=period,
            status=GSTRReconciliationStatus.NOT_COMPARABLE,
            comparison_source=ReconciliationDataSource.UNPROVIDED,
            is_portal_verified=False,
            is_comparison_performed=False,
            is_outward_compared=False,
            is_itc_compared=False,
            is_outward_matched=False,
            is_itc_matched=False,
            requires_policy_approval=False,
            statutory_determination_claim=False,
            drc01b_risk=False,
            drc01c_risk=False,
            variance_reasons=[
                "GSTR-3B filed return data was not provided for tax period "
                f"{period.tax_period}. Independent return reconciliation "
                "cannot be performed."
            ],
            gstr1_outward=gstr1_outward,
            gstr3b_outward=None,
            outward_discrepancy=None,
            itc_books=itc_books,
            itc_gstr3b=None,
            itc_discrepancy=None,
            gstr1_total_turnover=gstr1_total_turnover,
            gstr3b_total_turnover=None,
            turnover_discrepancy=None,
        )

    def _compute_reconciliation_discrepancy(
        self,
        summary_a: GSTAmountSummary,
        summary_b: GSTAmountSummary,
    ) -> GSTRReconciliationDiscrepancy:
        """Compute component discrepancy between two GST summaries."""
        return GSTRReconciliationDiscrepancy(
            taxable_value=self._money(
                summary_a.taxable_value - summary_b.taxable_value
            ),
            cgst_amount=self._money(summary_a.cgst_amount - summary_b.cgst_amount),
            sgst_amount=self._money(summary_a.sgst_amount - summary_b.sgst_amount),
            igst_amount=self._money(summary_a.igst_amount - summary_b.igst_amount),
            utgst_amount=self._money(
                summary_a.utgst_amount - summary_b.utgst_amount
            ),
            cess_amount=self._money(summary_a.cess_amount - summary_b.cess_amount),
            tax_amount=self._money(summary_a.tax_amount - summary_b.tax_amount),
            total_amount=self._money(
                summary_a.total_amount - summary_b.total_amount
            ),
        )

    def _evaluate_tolerance_risk(
        self,
        *,
        override_present: bool,
        excess_amount: Decimal,
        base_amount: Decimal,
    ) -> bool:
        """Evaluate if variance breaches internal advisory tolerance limits."""
        if not override_present:
            return False
        internal_tolerance_amount = Decimal("25000.00")
        internal_tolerance_ratio = Decimal("0.20")
        if excess_amount <= internal_tolerance_amount:
            return False
        if base_amount <= ZERO_AMOUNT:
            return True
        return (excess_amount / base_amount) > internal_tolerance_ratio

    def _determine_reconciliation_status(
        self,
        *,
        drc01b_risk: bool,
        drc01c_risk: bool,
        is_outward_compared: bool,
        is_itc_compared: bool,
        is_outward_matched: bool,
        is_itc_matched: bool,
    ) -> tuple[GSTRReconciliationStatus, bool]:
        """Determine reconciliation status and policy approval requirement."""
        if drc01b_risk:
            return GSTRReconciliationStatus.DRC01B_RISK, True
        if drc01c_risk:
            return GSTRReconciliationStatus.DRC01C_RISK, True
        if is_outward_compared and not is_outward_matched:
            return GSTRReconciliationStatus.DISCREPANCY_DETECTED, False
        if is_itc_compared and not is_itc_matched:
            return GSTRReconciliationStatus.DISCREPANCY_DETECTED, False
        if is_outward_compared and is_itc_compared:
            return GSTRReconciliationStatus.MATCHED, False
        return GSTRReconciliationStatus.NOT_COMPARABLE, False

    def _validate_override_amounts(
        self,
        override: GSTAmountSummary,
        override_type: str,
    ) -> None:
        """Validate non-negative and consistent tax component breakdown."""
        for name, amt in (
            ("taxable_value", override.taxable_value),
            ("cgst_amount", override.cgst_amount),
            ("sgst_amount", override.sgst_amount),
            ("igst_amount", override.igst_amount),
            ("utgst_amount", override.utgst_amount),
            ("cess_amount", override.cess_amount),
            ("tax_amount", override.tax_amount),
            ("total_amount", override.total_amount),
        ):
            if amt < ZERO_AMOUNT:
                raise GSTComparisonInputValidationException(
                    f"GSTR-3B {override_type} '{name}' cannot be negative: ₹{amt}."
                )
        comp_sum = (
            override.cgst_amount
            + override.sgst_amount
            + override.igst_amount
            + override.utgst_amount
            + override.cess_amount
        )
        if comp_sum not in (ZERO_AMOUNT, override.tax_amount):
            raise GSTComparisonInputValidationException(
                f"Contradictory GSTR-3B {override_type} input: tax amount "
                f"₹{override.tax_amount} does not match sum of individual "
                f"components ₹{comp_sum}."
            )

    def _reconcile_outward(
        self,
        *,
        gstr1_outward: GSTAmountSummary,
        gstr1_total_turnover: Decimal,
        override: GSTAmountSummary | None,
        non_taxable_turnover: Decimal,
    ) -> tuple[
        bool,
        GSTAmountSummary | None,
        GSTRReconciliationDiscrepancy | None,
        Decimal | None,
        Decimal | None,
        bool,
        bool,
    ]:
        """Reconcile GSTR-1 outward liability against GSTR-3B override."""
        if override is None:
            return (
                False,
                None,
                None,
                None,
                None,
                False,
                False,
            )
        gstr3b_outward = self._rounded_summary(override)
        gstr3b_total_turnover = self._money(
            gstr3b_outward.taxable_value + non_taxable_turnover
        )
        outward_discrepancy = self._compute_reconciliation_discrepancy(
            gstr1_outward, gstr3b_outward
        )
        turnover_discrepancy = self._money(
            gstr1_total_turnover - gstr3b_total_turnover
        )
        is_outward_matched = (
            outward_discrepancy.taxable_value == ZERO_AMOUNT
            and outward_discrepancy.cgst_amount == ZERO_AMOUNT
            and outward_discrepancy.sgst_amount == ZERO_AMOUNT
            and outward_discrepancy.igst_amount == ZERO_AMOUNT
            and outward_discrepancy.utgst_amount == ZERO_AMOUNT
            and outward_discrepancy.cess_amount == ZERO_AMOUNT
            and outward_discrepancy.tax_amount == ZERO_AMOUNT
            and outward_discrepancy.total_amount == ZERO_AMOUNT
            and turnover_discrepancy == ZERO_AMOUNT
        )
        drc01b_risk = self._evaluate_tolerance_risk(
            override_present=True,
            excess_amount=outward_discrepancy.tax_amount,
            base_amount=gstr3b_outward.tax_amount,
        )
        return (
            True,
            gstr3b_outward,
            outward_discrepancy,
            gstr3b_total_turnover,
            turnover_discrepancy,
            is_outward_matched,
            drc01b_risk,
        )

    def _reconcile_itc(
        self,
        *,
        itc_books: GSTAmountSummary,
        override: GSTAmountSummary | None,
    ) -> tuple[
        bool,
        GSTAmountSummary | None,
        GSTRReconciliationDiscrepancy | None,
        bool,
        bool,
    ]:
        """Reconcile inward books ITC against GSTR-3B claimed ITC override."""
        if override is None:
            return (
                False,
                None,
                None,
                False,
                False,
            )
        itc_gstr3b = self._rounded_summary(override)
        itc_discrepancy = self._compute_reconciliation_discrepancy(
            itc_books, itc_gstr3b
        )
        is_itc_matched = (
            itc_discrepancy.taxable_value == ZERO_AMOUNT
            and itc_discrepancy.cgst_amount == ZERO_AMOUNT
            and itc_discrepancy.sgst_amount == ZERO_AMOUNT
            and itc_discrepancy.igst_amount == ZERO_AMOUNT
            and itc_discrepancy.utgst_amount == ZERO_AMOUNT
            and itc_discrepancy.cess_amount == ZERO_AMOUNT
            and itc_discrepancy.tax_amount == ZERO_AMOUNT
            and itc_discrepancy.total_amount == ZERO_AMOUNT
        )
        itc_excess = self._money(itc_gstr3b.tax_amount - itc_books.tax_amount)
        drc01c_risk = self._evaluate_tolerance_risk(
            override_present=True,
            excess_amount=itc_excess,
            base_amount=itc_books.tax_amount,
        )
        return (
            True,
            itc_gstr3b,
            itc_discrepancy,
            is_itc_matched,
            drc01c_risk,
        )

    def _collect_component_discrepancies(
        self,
        discrepancy: GSTRReconciliationDiscrepancy | None,
        prefix: str,
    ) -> list[str]:
        """Compile discrepancy strings for individual tax components."""
        if discrepancy is None:
            return []
        components = [
            ("IGST", discrepancy.igst_amount),
            ("CGST", discrepancy.cgst_amount),
            ("SGST", discrepancy.sgst_amount),
            ("UTGST", discrepancy.utgst_amount),
            ("Cess", discrepancy.cess_amount),
        ]
        return [
            f"{prefix} {name} discrepancy: ₹{amt}"
            for name, amt in components
            if amt not in (None, ZERO_AMOUNT)
        ]

    def _collect_variance_reasons(
        self,
        *,
        has_liability_override: bool,
        has_itc_override: bool,
        is_outward_matched: bool,
        is_itc_matched: bool,
        outward_discrepancy: GSTRReconciliationDiscrepancy | None,
        itc_discrepancy: GSTRReconciliationDiscrepancy | None,
        turnover_discrepancy: Decimal | None,
    ) -> list[str]:
        """Compile explanatory reasons for return discrepancies."""
        reasons: list[str] = []
        if not has_liability_override:
            reasons.append("GSTR-3B outward liability data unprovided.")
        elif not is_outward_matched and outward_discrepancy is not None:
            if (
                outward_discrepancy.tax_amount is not None
                and outward_discrepancy.tax_amount > ZERO_AMOUNT
            ):
                reasons.append(
                    "GSTR-1 outward tax liability exceeds GSTR-3B by "
                    f"₹{outward_discrepancy.tax_amount}"
                )
            elif (
                outward_discrepancy.tax_amount is not None
                and outward_discrepancy.tax_amount < ZERO_AMOUNT
            ):
                reasons.append(
                    "GSTR-3B outward tax exceeds GSTR-1 by "
                    f"₹{abs(outward_discrepancy.tax_amount)}"
                )
            reasons.extend(
                self._collect_component_discrepancies(
                    outward_discrepancy, "Outward"
                )
            )
            if turnover_discrepancy is not None and turnover_discrepancy != ZERO_AMOUNT:
                reasons.append(f"Turnover discrepancy: ₹{turnover_discrepancy}")

        if not has_itc_override:
            reasons.append("GSTR-3B claimed ITC data unprovided.")
        elif not is_itc_matched and itc_discrepancy is not None:
            if (
                itc_discrepancy.tax_amount is not None
                and itc_discrepancy.tax_amount < ZERO_AMOUNT
            ):
                reasons.append(
                    "GSTR-3B claimed ITC exceeds inward books ITC by "
                    f"₹{abs(itc_discrepancy.tax_amount)}"
                )
            elif (
                itc_discrepancy.tax_amount is not None
                and itc_discrepancy.tax_amount > ZERO_AMOUNT
            ):
                reasons.append(
                    "Inward books ITC exceeds GSTR-3B claimed ITC by "
                    f"₹{itc_discrepancy.tax_amount}"
                )
            reasons.extend(
                self._collect_component_discrepancies(itc_discrepancy, "ITC")
            )
        return reasons

    async def generate_hsn_summary(

        self,
        request: GSTReportRequest,
    ) -> list[HSNReportLine]:
        """Generate HSN summary from posted sales lines."""
        _period, sales, _purchases, _expenses = await self._load_sources(request)
        return self._hsn_summary(sales)

    async def generate_tax_liability(
        self,
        request: GSTReportRequest,
    ) -> GSTSummaryReport:
        """Generate tax liability summary."""
        period, sales, _purchases, _expenses = await self._load_sources(request)
        return GSTSummaryReport(period=period, summary=self._summarize_documents(sales))

    async def generate_purchase_summary(
        self,
        request: GSTReportRequest,
    ) -> GSTSummaryReport:
        """Generate purchase GST summary."""
        period, _sales, purchases, _expenses = await self._load_sources(request)
        return GSTSummaryReport(
            period=period,
            summary=self._summarize_documents(purchases),
        )

    async def generate_sales_summary(
        self,
        request: GSTReportRequest,
    ) -> GSTSummaryReport:
        """Generate sales GST summary."""
        period, sales, _purchases, _expenses = await self._load_sources(request)
        return GSTSummaryReport(period=period, summary=self._summarize_documents(sales))

    async def generate_audit_report(
        self,
        request: GSTReportRequest,
    ) -> GSTAuditReportResponse:
        """Generate GST audit report from source document consistency checks."""
        period, sales, purchases, expenses = await self._load_sources(request)
        issues = [
            *self._audit_documents(sales, "sales_invoice"),
            *self._audit_documents(purchases, "purchase_invoice"),
            *self._audit_documents(expenses, "expense"),
        ]
        report = GSTAuditReportResponse(
            period=period,
            issues=issues,
            issue_count=len(issues),
        )
        await self._event_dispatcher.dispatch(
            GSTAuditCompletedEvent(
                business_id=period.business_id,
                tax_period=period.tax_period,
                issue_count=len(issues),
            )
        )
        return report

    def _sanitize_csv_cell(self, val: object) -> object:
        """Neutralize spreadsheet formula injection for untrusted cell values."""
        if val is None:
            return ""
        if not isinstance(val, str):
            return val
        if val and val[0] in ("=", "+", "-", "@", "\t", "\r"):
            try:
                Decimal(val)
                return val
            except (InvalidOperation, ValueError):
                return f"'{val}"
        return val

    def export_csv(self, report: BaseModel | list[BaseModel]) -> str:
        """Export a GST report or report lines as CSV with formula injection defense."""
        rows = report if isinstance(report, list) else [report]
        output = io.StringIO()
        flattened = [self._flatten(row.model_dump(mode="json")) for row in rows]
        if not flattened:
            return ""
        sanitized_rows = [
            {k: self._sanitize_csv_cell(v) for k, v in row.items()}
            for row in flattened
        ]
        writer = csv.DictWriter(
            output, fieldnames=list(sanitized_rows[0].keys())
        )
        writer.writeheader()
        writer.writerows(sanitized_rows)
        return output.getvalue()

    async def _load_sources(
        self,
        request: GSTReportRequest,
    ) -> tuple[
        GSTReportPeriod,
        list[SalesInvoice],
        list[PurchaseInvoice],
        list[Expense],
    ]:
        """Load source documents for a resolved report period."""
        validated = GSTReportRequest.model_validate(request)
        period = self._resolve_period(validated)
        async with self._unit_of_work_factory() as uow:
            raw_sales = await uow.gst_compliance.list_sales(
                business_id=validated.business_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
            raw_purchases = await uow.gst_compliance.list_purchases(
                business_id=validated.business_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
            raw_expenses = await uow.gst_compliance.list_expenses(
                business_id=validated.business_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
            await uow.commit()

        sales = [
            s
            for s in raw_sales
            if getattr(s, "status", None) in POSTED_SALES_STATUSES
        ]
        purchases = [
            p
            for p in raw_purchases
            if getattr(p, "status", None) in POSTED_PURCHASE_STATUSES
        ]
        expenses = [
            e
            for e in raw_expenses
            if getattr(e, "status", None) in POSTED_EXPENSE_STATUSES
        ]
        return period, sales, purchases, expenses

    def _resolve_period(self, request: GSTReportRequest) -> GSTReportPeriod:
        """Resolve period dates and financial year from request."""
        if request.filing_frequency == GSTFilingFrequency.QUARTERLY:
            match = re.match(r"^(\d{4})-Q([1-4])$", request.tax_period)
            if not match:
                raise GSTInvalidPeriodException(
                    f"Invalid quarterly tax period: '{request.tax_period}'. "
                    "Expected YYYY-QN (e.g. 2026-Q1).",
                    details={
                        "tax_period": request.tax_period,
                        "filing_frequency": request.filing_frequency.value,
                    },
                )
            year = int(match.group(1))
            quarter = int(match.group(2))
            start_month = (
                ((quarter - 1) * MONTHS_PER_QUARTER)
                + FINANCIAL_YEAR_START_MONTH
            )
            start_year = year
            if start_month > DECEMBER:
                start_month -= DECEMBER
                start_year += 1
            end_month = start_month + MONTHS_PER_QUARTER - 1
            end_year = start_year
            if end_month > DECEMBER:
                end_month -= DECEMBER
                end_year += 1
            start_date = date(start_year, start_month, 1)
            end_date = self._month_end(end_year, end_month)
        else:
            match = re.match(r"^(\d{4})-(0[1-9]|1[0-2])$", request.tax_period)
            if not match:
                raise GSTInvalidPeriodException(
                    f"Invalid monthly tax period: '{request.tax_period}'. "
                    "Expected YYYY-MM (e.g. 2026-04).",
                    details={
                        "tax_period": request.tax_period,
                        "filing_frequency": request.filing_frequency.value,
                    },
                )
            year = int(match.group(1))
            month = int(match.group(2))
            start_date = date(year, month, 1)
            end_date = self._month_end(year, month)
        financial_year = (
            f"{start_date.year}-{start_date.year + 1}"
            if start_date.month >= FINANCIAL_YEAR_START_MONTH
            else f"{start_date.year - 1}-{start_date.year}"
        )
        return GSTReportPeriod(
            business_id=request.business_id,
            financial_year=financial_year,
            tax_period=request.tax_period,
            filing_frequency=request.filing_frequency,
            start_date=start_date,
            end_date=end_date,
            generated_at=datetime.now(tz=UTC),
        )

    def _summarize_documents(self, documents: Sequence[object]) -> GSTAmountSummary:
        """Summarize stored GST values from source documents."""
        summary = GSTAmountSummary()
        for document in documents:
            summary.taxable_value += getattr(
                document,
                "taxable_amount",
                getattr(document, "subtotal", ZERO_AMOUNT),
            )
            summary.tax_amount += getattr(document, "tax_amount", ZERO_AMOUNT)
            summary.total_amount += getattr(document, "total_amount", ZERO_AMOUNT)
            for line in getattr(document, "lines", []):
                summary.cgst_amount += self._line_component(line, "cgst_amount")
                summary.sgst_amount += self._line_component(line, "sgst_amount")
                summary.igst_amount += self._line_component(line, "igst_amount")
                summary.utgst_amount += self._line_component(line, "utgst_amount")
                summary.cess_amount += self._line_component(line, "cess_amount")
        return self._rounded_summary(summary)

    def _is_b2b_customer(self, customer: object | None) -> bool:
        """Return True unless customer is explicitly present and lacks a valid GSTIN."""
        if customer is None:
            return True
        gstin = getattr(customer, "gstin", None)
        return bool(gstin and str(gstin).strip())

    def _line_tax_amount(self, line: object) -> Decimal:
        """Return total GST components for a line."""
        return (
            self._line_component(line, "cgst_amount")
            + self._line_component(line, "sgst_amount")
            + self._line_component(line, "igst_amount")
            + self._line_component(line, "utgst_amount")
            + self._line_component(line, "cess_amount")
        )

    def _line_taxable_value(self, line: object) -> Decimal:
        """Return net taxable value for a line."""
        taxable_val = getattr(line, "taxable_value", None)
        if taxable_val is not None:
            return self._money(taxable_val)
        taxable_amt = getattr(line, "taxable_amount", None)
        if taxable_amt is not None:
            return self._money(taxable_amt)
        line_tax = self._line_tax_amount(line)
        line_total = getattr(line, "line_total", None)
        if line_total is not None and line_total > ZERO_AMOUNT:
            return self._money(max(line_total - line_tax, ZERO_AMOUNT))
        qty = getattr(line, "quantity", ZERO_AMOUNT)
        price = getattr(line, "unit_price", getattr(line, "unit_cost", ZERO_AMOUNT))
        discount = getattr(line, "discount", ZERO_AMOUNT)
        return self._money(max((qty * price) - discount, ZERO_AMOUNT))

    def _classify_line(
        self,
        line: object,
        *,
        is_b2b: bool,
        is_export: bool,
    ) -> SupplyCategory:
        """Determine statutory supply category for a sales invoice line."""
        supply_type = getattr(line, "supply_type", None)
        if (
            is_export
            or getattr(line, "is_zero_rated", False)
            or supply_type in {GSTSupplyType.ZERO_RATED, "zero_rated"}
        ):
            return SupplyCategory.EXPORTS

        line_tax = self._line_tax_amount(line)
        tax_rate = getattr(line, "tax_rate", None)
        is_taxable = line_tax > ZERO_AMOUNT or (
            tax_rate is not None and tax_rate > ZERO_AMOUNT
        )
        if is_taxable:
            return SupplyCategory.B2B if is_b2b else SupplyCategory.B2C

        if getattr(line, "is_exempt", False) or supply_type in {
            GSTSupplyType.EXEMPT,
            "exempt",
        }:
            return SupplyCategory.EXEMPT

        return SupplyCategory.NIL_RATED

    def _classify_document_without_lines(
        self,
        document: object,
        *,
        is_b2b: bool,
        is_export: bool,
    ) -> SupplyCategory:
        """Determine statutory supply category for a sales document without lines."""
        supply_type = getattr(document, "supply_type", None)
        if (
            is_export
            or getattr(document, "is_zero_rated", False)
            or supply_type in {GSTSupplyType.ZERO_RATED, "zero_rated"}
        ):
            return SupplyCategory.EXPORTS

        tax_amount = getattr(document, "tax_amount", ZERO_AMOUNT)
        tax_rate = getattr(document, "tax_rate", None)
        is_taxable = tax_amount > ZERO_AMOUNT or (
            tax_rate is not None and tax_rate > ZERO_AMOUNT
        )
        if is_taxable:
            return SupplyCategory.B2B if is_b2b else SupplyCategory.B2C

        if getattr(document, "is_exempt", False) or supply_type in {
            GSTSupplyType.EXEMPT,
            "exempt",
        }:
            return SupplyCategory.EXEMPT

        return SupplyCategory.NIL_RATED

    def _classify_and_summarize_sales(
        self,
        sales: Sequence[object],
    ) -> dict[SupplyCategory, GSTAmountSummary]:
        """Aggregate sales into statutory supply categories at line-level precision."""
        summaries: dict[SupplyCategory, GSTAmountSummary] = {
            category: GSTAmountSummary() for category in SupplyCategory
        }

        for invoice in sales:
            customer = getattr(invoice, "customer", None)
            is_b2b = self._is_b2b_customer(customer)
            is_export = bool(getattr(invoice, "is_export", False))
            lines = getattr(invoice, "lines", None)

            if lines:
                for line in lines:
                    category = self._classify_line(
                        line,
                        is_b2b=is_b2b,
                        is_export=is_export,
                    )
                    target = summaries[category]
                    line_taxable = self._line_taxable_value(line)
                    cgst = self._line_component(line, "cgst_amount")
                    sgst = self._line_component(line, "sgst_amount")
                    igst = self._line_component(line, "igst_amount")
                    utgst = self._line_component(line, "utgst_amount")
                    cess = self._line_component(line, "cess_amount")
                    line_tax = cgst + sgst + igst + utgst + cess
                    line_total = getattr(line, "line_total", None)
                    line_total_amt = (
                        self._money(line_total)
                        if line_total is not None
                        else self._money(line_taxable + line_tax)
                    )

                    target.taxable_value += line_taxable
                    target.cgst_amount += cgst
                    target.sgst_amount += sgst
                    target.igst_amount += igst
                    target.utgst_amount += utgst
                    target.cess_amount += cess
                    target.tax_amount += line_tax
                    target.total_amount += line_total_amt
            else:
                category = self._classify_document_without_lines(
                    invoice,
                    is_b2b=is_b2b,
                    is_export=is_export,
                )
                target = summaries[category]
                target.taxable_value += getattr(
                    invoice,
                    "taxable_amount",
                    getattr(invoice, "subtotal", ZERO_AMOUNT),
                )
                target.cgst_amount += getattr(invoice, "cgst_amount", ZERO_AMOUNT)
                target.sgst_amount += getattr(invoice, "sgst_amount", ZERO_AMOUNT)
                target.igst_amount += getattr(invoice, "igst_amount", ZERO_AMOUNT)
                target.utgst_amount += getattr(invoice, "utgst_amount", ZERO_AMOUNT)
                target.cess_amount += getattr(invoice, "cess_amount", ZERO_AMOUNT)
                target.tax_amount += getattr(invoice, "tax_amount", ZERO_AMOUNT)
                target.total_amount += getattr(invoice, "total_amount", ZERO_AMOUNT)

        return {
            category: self._rounded_summary(summary)
            for category, summary in summaries.items()
        }

    def _nil_or_exempt_summary(self, documents: Sequence[object]) -> GSTAmountSummary:
        """Summarize documents with taxable value but no GST amount."""
        return self._summarize_documents(
            [
                document
                for document in documents
                if getattr(document, "tax_amount", ZERO_AMOUNT) == ZERO_AMOUNT
            ]
        )

    def _input_tax_credit(
        self,
        purchases: list[PurchaseInvoice],
        expenses: list[Expense],
    ) -> GSTAmountSummary:
        """Summarize eligible ITC from purchases and expenses."""
        return self._summarize_documents([*purchases, *expenses])

    def _hsn_summary(self, documents: Sequence[object]) -> list[HSNReportLine]:
        """Generate HSN summary from stored source line values."""
        grouped: dict[str, HSNReportLine] = {}
        for document in documents:
            for line in getattr(document, "lines", []):
                hsn_code = getattr(line, "hsn_code", None) or "UNMAPPED"
                quantity = getattr(line, "quantity", ZERO_AMOUNT)
                taxable_value = self._line_taxable_value(line)
                existing = grouped.setdefault(
                    hsn_code,
                    HSNReportLine(
                        hsn_code=hsn_code,
                        description=getattr(line, "description", "Unmapped"),
                        quantity=ZERO_AMOUNT,
                    ),
                )
                existing.quantity += quantity
                existing.taxable_value += taxable_value
                existing.cgst_amount += self._line_component(line, "cgst_amount")
                existing.sgst_amount += self._line_component(line, "sgst_amount")
                existing.igst_amount += self._line_component(line, "igst_amount")
                existing.utgst_amount += self._line_component(line, "utgst_amount")
                existing.cess_amount += self._line_component(line, "cess_amount")
                existing.tax_amount = (
                    existing.cgst_amount
                    + existing.sgst_amount
                    + existing.igst_amount
                    + existing.utgst_amount
                    + existing.cess_amount
                )
                line_total = getattr(line, "line_total", None)
                line_total_amt = (
                    self._money(line_total)
                    if line_total is not None
                    else self._money(taxable_value + self._line_tax_amount(line))
                )
                existing.total_amount += line_total_amt
        return [self._rounded_hsn(line) for line in grouped.values()]

    def _audit_documents(
        self,
        documents: Sequence[object],
        source_type: str,
    ) -> list[GSTAuditIssue]:
        """Detect GST consistency issues in source documents."""
        issues: list[GSTAuditIssue] = []
        for document in documents:
            document_id = document.id  # type: ignore[attr-defined]
            if not isinstance(document_id, uuid.UUID):
                continue
            tax_amount = getattr(document, "tax_amount", ZERO_AMOUNT)
            total_amount = getattr(document, "total_amount", ZERO_AMOUNT)
            taxable_value = getattr(
                document,
                "taxable_amount",
                getattr(document, "subtotal", ZERO_AMOUNT),
            )
            component_tax = sum(
                (
                    self._line_component(line, "cgst_amount")
                    + self._line_component(line, "sgst_amount")
                    + self._line_component(line, "igst_amount")
                    + self._line_component(line, "utgst_amount")
                    + self._line_component(line, "cess_amount")
                )
                for line in getattr(document, "lines", [])
            )
            if tax_amount > ZERO_AMOUNT and component_tax == ZERO_AMOUNT:
                issues.append(
                    GSTAuditIssue(
                        source_type=source_type,
                        source_id=document_id,
                        code="missing_gst_breakdown",
                        message="Document has tax amount but no GST components.",
                    )
                )
            if component_tax not in (ZERO_AMOUNT, tax_amount):
                issues.append(
                    GSTAuditIssue(
                        source_type=source_type,
                        source_id=document_id,
                        code="mismatched_tax",
                        message="Document GST components do not match tax amount.",
                    )
                )
            if (
                taxable_value < ZERO_AMOUNT
                or tax_amount < ZERO_AMOUNT
                or total_amount < ZERO_AMOUNT
            ):
                issues.append(
                    GSTAuditIssue(
                        source_type=source_type,
                        source_id=document_id,
                        code="negative_values",
                        message="Document contains negative GST values.",
                    )
                )
            if taxable_value + tax_amount != total_amount:
                issues.append(
                    GSTAuditIssue(
                        source_type=source_type,
                        source_id=document_id,
                        code="unbalanced_document",
                        message="Document taxable value plus tax does not equal total.",
                    )
                )
            if source_type == "sales_invoice":
                lines = getattr(document, "lines", [])
                if lines:
                    has_unclassified_zero_tax = any(
                        self._line_taxable_value(line) > ZERO_AMOUNT
                        and self._line_tax_amount(line) == ZERO_AMOUNT
                        and (
                            getattr(line, "tax_rate", None) is None
                            or getattr(line, "tax_rate", None) == ZERO_AMOUNT
                        )
                        and not getattr(line, "is_exempt", False)
                        and not getattr(line, "is_zero_rated", False)
                        and not getattr(line, "is_nil_rated", False)
                        and getattr(line, "supply_type", None) is None
                        for line in lines
                    )
                    if has_unclassified_zero_tax:
                        issues.append(
                            GSTAuditIssue(
                                source_type=source_type,
                                source_id=document_id,
                                code="unclassified_zero_tax_supply",
                                message=(
                                    "Document contains zero-tax supply line without "
                                    "authoritative classification metadata."
                                ),
                            )
                        )
                elif (
                    taxable_value > ZERO_AMOUNT
                    and tax_amount == ZERO_AMOUNT
                    and (
                        getattr(document, "tax_rate", None) is None
                        or getattr(document, "tax_rate", None) == ZERO_AMOUNT
                    )
                    and not getattr(document, "is_exempt", False)
                    and not getattr(document, "is_zero_rated", False)
                    and not getattr(document, "is_nil_rated", False)
                    and getattr(document, "supply_type", None) is None
                ):
                    issues.append(
                        GSTAuditIssue(
                            source_type=source_type,
                            source_id=document_id,
                            code="unclassified_zero_tax_supply",
                            message=(
                                "Document contains zero-tax supply without "
                                "authoritative classification metadata."
                            ),
                        )
                    )
        return issues

    async def _publish_return(
        self,
        period: GSTReportPeriod,
        report_type: str,
    ) -> None:
        """Publish GST return generated event."""
        await self._event_dispatcher.dispatch(
            GSTReturnGeneratedEvent(
                business_id=period.business_id,
                tax_period=period.tax_period,
                report_type=report_type,
            )
        )

    def _rounded_summary(self, summary: GSTAmountSummary) -> GSTAmountSummary:
        """Round a GST summary."""
        return GSTAmountSummary(
            taxable_value=self._money(summary.taxable_value),
            cgst_amount=self._money(summary.cgst_amount),
            sgst_amount=self._money(summary.sgst_amount),
            igst_amount=self._money(summary.igst_amount),
            utgst_amount=self._money(summary.utgst_amount),
            cess_amount=self._money(summary.cess_amount),
            tax_amount=self._money(summary.tax_amount),
            total_amount=self._money(summary.total_amount),
        )

    def _rounded_hsn(self, line: HSNReportLine) -> HSNReportLine:
        """Round an HSN summary line."""
        summary = self._rounded_summary(line)
        return HSNReportLine(
            hsn_code=line.hsn_code,
            description=line.description,
            quantity=line.quantity,
            **summary.model_dump(),
        )

    def _flatten(self, payload: dict[str, object]) -> dict[str, object]:
        """Flatten nested report payload for CSV export."""
        flattened: dict[str, object] = {}
        for key, value in payload.items():
            if isinstance(value, dict):
                for child_key, child_value in value.items():
                    flattened[f"{key}.{child_key}"] = (
                        "" if child_value is None else child_value
                    )
            elif value is None and key in (
                "gstr3b_outward",
                "outward_discrepancy",
                "itc_gstr3b",
                "itc_discrepancy",
            ):
                for child_key in (
                    "taxable_value",
                    "cgst_amount",
                    "sgst_amount",
                    "igst_amount",
                    "utgst_amount",
                    "cess_amount",
                    "tax_amount",
                    "total_amount",
                ):
                    flattened[f"{key}.{child_key}"] = ""
            else:
                flattened[key] = "" if value is None else value
        return flattened

    def _line_component(self, line: object, field_name: str) -> Decimal:
        """Return a GST component value from a line."""
        return getattr(line, field_name, ZERO_AMOUNT) or ZERO_AMOUNT

    def _month_end(self, year: int, month: int) -> date:
        """Return the final date for a month."""
        if month == DECEMBER:
            return date(year, DECEMBER, 31)
        return date(year, month, monthrange(year, month)[1])

    def _money(self, value: Decimal) -> Decimal:
        """Round money to two decimal places."""
        return value.quantize(Decimal("0.01"))
