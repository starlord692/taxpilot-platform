"""GST compliance report schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    utgst_amount: Decimal = Decimal("0.00")
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


class GSTRReconciliationDiscrepancy(BaseModel):
    """Discrepancy amounts between return sources."""

    taxable_value: Decimal | None = None
    cgst_amount: Decimal | None = None
    sgst_amount: Decimal | None = None
    igst_amount: Decimal | None = None
    utgst_amount: Decimal | None = None
    cess_amount: Decimal | None = None
    tax_amount: Decimal | None = None
    total_amount: Decimal | None = None


class ReconciliationDataSource(StrEnum):
    """Provenance source of reconciliation comparison data."""

    UNPROVIDED = "unprovided"
    USER_SUPPLIED = "user_supplied"
    GOVERNMENT_PORTAL = "government_portal"


class GSTRReconciliationStatus(StrEnum):
    """Reconciliation evaluation status."""

    MATCHED = "matched"
    DRC01B_RISK = "drc01b_risk"
    DRC01C_RISK = "drc01c_risk"
    DISCREPANCY_DETECTED = "discrepancy_detected"
    NOT_COMPARABLE = "not_comparable"


class GSTRReconciliationReport(BaseModel):
    """GSTR-1 vs GSTR-3B and ITC Reconciliation Report.

    Reconciles GSTR-1 outward liability vs GSTR-3B and inward books ITC.
    Internal variance alerts are non-statutory advisory heuristics,
    not official GST portal determinations under Rule 88C/88D.
    """

    period: GSTReportPeriod
    status: GSTRReconciliationStatus
    comparison_source: ReconciliationDataSource = Field(
        default=ReconciliationDataSource.UNPROVIDED,
        description=(
            "Provenance of comparison return data: 'unprovided',"
            " 'user_supplied', or 'government_portal'."
        ),
    )
    is_portal_verified: bool = Field(
        default=False,
        description=(
            "Whether comparison data is verified by an authorized"
            " government portal provider."
        ),
    )
    is_comparison_performed: bool = Field(
        default=False,
        description="False if comparison source data is unprovided or missing.",
    )
    is_outward_compared: bool = Field(
        default=False,
        description="True if outward liability comparison was performed.",
    )
    is_itc_compared: bool = Field(
        default=False,
        description="True if inward ITC comparison was performed.",
    )
    is_outward_matched: bool = Field(
        default=False,
        description="True if outward liability matched comparison data.",
    )
    is_itc_matched: bool = Field(
        default=False,
        description="True if inward ITC matched comparison data.",
    )
    requires_policy_approval: bool = Field(
        default=False,
        description=(
            "True if internal variance tolerance is exceeded requiring"
            " policy approval."
        ),
    )
    statutory_determination_claim: bool = Field(
        default=False,
        description=(
            "Always False: TaxPilot internal comparison is not an official"
            " GST portal determination."
        ),
    )
    drc01b_risk: bool = Field(
        default=False,
        description=(
            "Advisory internal variance alert: GSTR-1 outward tax liability"
            " exceeds GSTR-3B by internal tolerance threshold. Not an official"
            " portal determination under Rule 88C."
        ),
    )
    drc01c_risk: bool = Field(
        default=False,
        description=(
            "Advisory internal variance alert: GSTR-3B ITC claimed exceeds books"
            " inward ITC by internal tolerance threshold. Not an official"
            " portal determination under Rule 88D."
        ),
    )
    variance_reasons: list[str] = Field(
        default_factory=list,
        description=(
            "Explicit list of detected variance reasons, directions, and"
            " affected components."
        ),
    )
    gstr1_outward: GSTAmountSummary
    gstr3b_outward: GSTAmountSummary | None = None
    outward_discrepancy: GSTRReconciliationDiscrepancy | None = None
    itc_books: GSTAmountSummary
    itc_gstr3b: GSTAmountSummary | None = None
    itc_discrepancy: GSTRReconciliationDiscrepancy | None = None
    gstr1_total_turnover: Decimal
    gstr3b_total_turnover: Decimal | None = None
    turnover_discrepancy: Decimal | None = None

    @model_validator(mode="after")
    def validate_invariants(self) -> "GSTRReconciliationReport":
        """Enforce trust-boundary, comparison lifecycle, and match invariants."""
        self._validate_trust_boundary()
        self._validate_match_integrity()
        self._validate_lifecycle_nullability()
        return self

    def _validate_trust_boundary(self) -> None:
        if (
            self.is_portal_verified
            and self.comparison_source != ReconciliationDataSource.GOVERNMENT_PORTAL
        ):
            raise ValueError(
                "is_portal_verified cannot be True unless comparison_source is "
                f"'{ReconciliationDataSource.GOVERNMENT_PORTAL.value}'."
            )
        if (
            self.comparison_source == ReconciliationDataSource.GOVERNMENT_PORTAL
            or self.is_portal_verified
        ):
            raise ValueError(
                "Government portal comparison source cannot be claimed without "
                "authorized server-side provider evidence."
            )

    def _validate_match_integrity(self) -> None:
        if self.statutory_determination_claim:
            raise ValueError(
                "statutory_determination_claim must always be False in TaxPilot AI."
            )
        if (
            self.status == GSTRReconciliationStatus.NOT_COMPARABLE
            and (self.drc01b_risk or self.drc01c_risk)
        ):
            raise ValueError(
                "status cannot be 'not_comparable' when drc01b_risk or "
                "drc01c_risk is True."
            )
        if self.status != GSTRReconciliationStatus.MATCHED:
            return
        if not self.is_comparison_performed:
            raise ValueError(
                "status cannot be 'matched' when comparison was not performed."
            )
        if not (
            self.is_outward_compared
            and self.is_itc_compared
            and self.is_outward_matched
            and self.is_itc_matched
        ):
            raise ValueError(
                "status 'matched' requires both outward and ITC to be compared "
                "and matched."
            )

    def _validate_lifecycle_nullability(self) -> None:
        if not self.is_comparison_performed:
            if self.is_outward_compared or self.is_itc_compared:
                raise ValueError(
                    "is_outward_compared and is_itc_compared must be False when "
                    "is_comparison_performed is False."
                )
            if self.is_outward_matched or self.is_itc_matched:
                raise ValueError(
                    "is_outward_matched and is_itc_matched must be False when "
                    "is_comparison_performed is False."
                )

        if not self.is_outward_compared:
            if self.is_outward_matched:
                raise ValueError(
                    "is_outward_matched cannot be True when outward was not compared."
                )
            if any(
                x is not None
                for x in (
                    self.gstr3b_outward,
                    self.outward_discrepancy,
                    self.gstr3b_total_turnover,
                    self.turnover_discrepancy,
                )
            ):
                raise ValueError(
                    "Outward comparison fields must be None when "
                    "is_outward_compared is False."
                )
        elif any(
            x is None
            for x in (
                self.gstr3b_outward,
                self.outward_discrepancy,
                self.gstr3b_total_turnover,
                self.turnover_discrepancy,
            )
        ):
            raise ValueError(
                "Outward comparison fields cannot be None when "
                "is_outward_compared is True."
            )

        if not self.is_itc_compared:
            if self.is_itc_matched:
                raise ValueError(
                    "is_itc_matched cannot be True when ITC was not compared."
                )
            if self.itc_gstr3b is not None or self.itc_discrepancy is not None:
                raise ValueError(
                    "ITC comparison fields must be None when is_itc_compared is False."
                )
        elif self.itc_gstr3b is None or self.itc_discrepancy is None:
            raise ValueError(
                "ITC comparison fields cannot be None when is_itc_compared is True."
            )



