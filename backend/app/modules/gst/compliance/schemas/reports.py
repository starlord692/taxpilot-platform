"""GST compliance report schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.modules.gst.compliance.models import GSTFilingFrequency


class GSTExportFormat(StrEnum):
    """Supported GST compliance export formats."""

    JSON = "json"
    CSV = "csv"


class GSTReportRequest(BaseModel):
    """Common GST compliance report request."""

    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID
    tax_period: str = Field(description="Monthly YYYY-MM or quarterly YYYY-QN period.")
    filing_frequency: GSTFilingFrequency = GSTFilingFrequency.MONTHLY


class GSTReportPeriod(BaseModel):
    """Resolved report period metadata."""

    business_id: uuid.UUID
    financial_year: str
    tax_period: str
    filing_frequency: GSTFilingFrequency
    start_date: date
    end_date: date
    generated_at: datetime


class GSTAmountSummary(BaseModel):
    """Reusable GST amount summary."""

    taxable_value: Decimal = Decimal("0.00")
    cgst_amount: Decimal = Decimal("0.00")
    sgst_amount: Decimal = Decimal("0.00")
    igst_amount: Decimal = Decimal("0.00")
    cess_amount: Decimal = Decimal("0.00")
    tax_amount: Decimal = Decimal("0.00")
    total_amount: Decimal = Decimal("0.00")


class HSNReportLine(GSTAmountSummary):
    """HSN summary report line."""

    hsn_code: str
    description: str
    quantity: Decimal


class GSTR1Report(BaseModel):
    """GSTR-1 report."""

    period: GSTReportPeriod
    b2b: GSTAmountSummary
    b2c: GSTAmountSummary
    exports: GSTAmountSummary
    credit_notes: GSTAmountSummary
    debit_notes: GSTAmountSummary
    nil_rated: GSTAmountSummary
    exempt: GSTAmountSummary
    hsn_summary: list[HSNReportLine]
    document_summary: dict[str, int]


class GSTR3BReport(BaseModel):
    """GSTR-3B report."""

    period: GSTReportPeriod
    outward_taxable_supplies: GSTAmountSummary
    zero_rated_supplies: GSTAmountSummary
    exempt_supplies: GSTAmountSummary
    inward_supplies: GSTAmountSummary
    reverse_charge: GSTAmountSummary
    input_tax_credit: GSTAmountSummary
    tax_liability: GSTAmountSummary
    net_gst_payable: Decimal


class ITCReport(BaseModel):
    """Input tax credit report."""

    period: GSTReportPeriod
    eligible_itc: GSTAmountSummary
    blocked_itc: GSTAmountSummary
    rcm_itc: GSTAmountSummary
    pending_itc: GSTAmountSummary


class GSTAuditIssue(BaseModel):
    """One GST audit issue."""

    source_type: str
    source_id: uuid.UUID
    code: str
    message: str


class GSTAuditReportResponse(BaseModel):
    """GST audit report response."""

    period: GSTReportPeriod
    issues: list[GSTAuditIssue]
    issue_count: int


class GSTSummaryReport(BaseModel):
    """Generic GST amount summary report."""

    period: GSTReportPeriod
    summary: GSTAmountSummary
