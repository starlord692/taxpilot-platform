"""GST Compliance Engine."""

import csv
import io
import uuid
from calendar import monthrange
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel

from app.common.events import EventDispatcher
from app.modules.expenses.models import Expense
from app.modules.gst.compliance.models import GSTFilingFrequency
from app.modules.gst.compliance.schemas import (
    GSTAmountSummary,
    GSTAuditIssue,
    GSTAuditReportResponse,
    GSTR1Report,
    GSTR3BReport,
    GSTReportPeriod,
    GSTReportRequest,
    GSTSummaryReport,
    HSNReportLine,
    ITCReport,
)
from app.modules.gst.events import GSTAuditCompletedEvent, GSTReturnGeneratedEvent
from app.modules.purchases.models import PurchaseInvoice
from app.modules.sales.models import SalesInvoice

ZERO_AMOUNT = Decimal("0.00")
FINANCIAL_YEAR_START_MONTH = 4
DECEMBER = 12
MONTHS_PER_QUARTER = 3


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
        report = GSTR1Report(
            period=period,
            b2b=self._summarize_documents(sales),
            b2c=GSTAmountSummary(),
            exports=GSTAmountSummary(),
            credit_notes=GSTAmountSummary(),
            debit_notes=GSTAmountSummary(),
            nil_rated=self._nil_or_exempt_summary(sales),
            exempt=GSTAmountSummary(),
            hsn_summary=self._hsn_summary(sales),
            document_summary={"sales_invoices": len(sales)},
        )
        await self._publish_return(period, "gstr1")
        return report

    async def generate_gstr3b(self, request: GSTReportRequest) -> GSTR3BReport:
        """Generate GSTR-3B from posted sales, purchases, and expenses."""
        period, sales, purchases, expenses = await self._load_sources(request)
        outward = self._summarize_documents(sales)
        inward = self._summarize_documents([*purchases, *expenses])
        itc = self._input_tax_credit(purchases, expenses)
        liability = GSTAmountSummary(
            taxable_value=outward.taxable_value,
            cgst_amount=outward.cgst_amount,
            sgst_amount=outward.sgst_amount,
            igst_amount=outward.igst_amount,
            cess_amount=outward.cess_amount,
            tax_amount=outward.tax_amount,
            total_amount=outward.tax_amount,
        )
        report = GSTR3BReport(
            period=period,
            outward_taxable_supplies=outward,
            zero_rated_supplies=GSTAmountSummary(),
            exempt_supplies=self._nil_or_exempt_summary(sales),
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

    def export_csv(self, report: BaseModel | list[BaseModel]) -> str:
        """Export a GST report or report lines as CSV."""
        rows = report if isinstance(report, list) else [report]
        output = io.StringIO()
        flattened = [self._flatten(row.model_dump(mode="json")) for row in rows]
        if not flattened:
            return ""
        writer = csv.DictWriter(output, fieldnames=list(flattened[0].keys()))
        writer.writeheader()
        writer.writerows(flattened)
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
            sales = await uow.gst_compliance.list_sales(
                business_id=validated.business_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
            purchases = await uow.gst_compliance.list_purchases(
                business_id=validated.business_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
            expenses = await uow.gst_compliance.list_expenses(
                business_id=validated.business_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
            await uow.commit()
        return period, sales, purchases, expenses

    def _resolve_period(self, request: GSTReportRequest) -> GSTReportPeriod:
        """Resolve period dates and financial year from request."""
        if request.filing_frequency == GSTFilingFrequency.QUARTERLY:
            year_text, quarter_text = request.tax_period.split("-Q", maxsplit=1)
            year = int(year_text)
            quarter = int(quarter_text)
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
            year_text, month_text = request.tax_period.split("-", maxsplit=1)
            year = int(year_text)
            month = int(month_text)
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
                summary.cess_amount += self._line_component(line, "cess_amount")
        return self._rounded_summary(summary)

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
                taxable_value = getattr(line, "line_total", ZERO_AMOUNT) - (
                    self._line_component(line, "cgst_amount")
                    + self._line_component(line, "sgst_amount")
                    + self._line_component(line, "igst_amount")
                    + self._line_component(line, "cess_amount")
                )
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
                existing.cess_amount += self._line_component(line, "cess_amount")
                existing.tax_amount = (
                    existing.cgst_amount
                    + existing.sgst_amount
                    + existing.igst_amount
                    + existing.cess_amount
                )
                existing.total_amount += getattr(line, "line_total", ZERO_AMOUNT)
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
                    flattened[f"{key}.{child_key}"] = child_value
            else:
                flattened[key] = value
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
