"""GST compliance API router."""

import uuid
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.responses import SuccessResponse
from app.modules.business.exceptions import BusinessNotMemberException
from app.modules.gst.compliance.api.dependencies import (
    get_gst_compliance_service,
    get_gst_compliance_unit_of_work,
)
from app.modules.gst.compliance.models import GSTFilingFrequency
from app.modules.gst.compliance.schemas import (
    GSTAmountSummary,
    GSTAuditReportResponse,
    GSTExportFormat,
    GSTR1Report,
    GSTR3BReport,
    GSTReportRequest,
    GSTRReconciliationReport,
    HSNReportLine,
    ITCReport,
)
from app.modules.gst.compliance.services import GSTComplianceService
from app.modules.gst.exceptions import GSTComparisonInputValidationException
from app.modules.identity.dependencies import CurrentUser

router = APIRouter(prefix="/compliance", tags=["GST Compliance"])
ComplianceServiceDep = Annotated[
    GSTComplianceService,
    Depends(get_gst_compliance_service),
]
ComplianceUnitOfWorkDep = Annotated[Any, Depends(get_gst_compliance_unit_of_work)]


@router.get(
    "/gstr1",
    response_model=SuccessResponse[GSTR1Report],
    status_code=status.HTTP_200_OK,
    summary="Generate GSTR-1",
    description="Generates GSTR-1 from posted GST source data.",
)
async def generate_gstr1(
    current_user: CurrentUser,
    uow: ComplianceUnitOfWorkDep,
    service: ComplianceServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    tax_period: Annotated[str, Query(description="Tax period, e.g. 2026-04.")],
    filing_frequency: GSTFilingFrequency = GSTFilingFrequency.MONTHLY,
    export_format: GSTExportFormat = GSTExportFormat.JSON,
) -> SuccessResponse[GSTR1Report] | Response:
    """Generate GSTR-1."""
    await _ensure_business_member(uow, business_id, current_user.id)
    report = await service.generate_gstr1(
        GSTReportRequest(
            business_id=business_id,
            tax_period=tax_period,
            filing_frequency=filing_frequency,
        )
    )
    return _format_response(service, report, export_format, "GSTR-1 generated")


@router.get(
    "/gstr3b",
    response_model=SuccessResponse[GSTR3BReport],
    status_code=status.HTTP_200_OK,
    summary="Generate GSTR-3B",
    description="Generates GSTR-3B from posted GST source data.",
)
async def generate_gstr3b(
    current_user: CurrentUser,
    uow: ComplianceUnitOfWorkDep,
    service: ComplianceServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    tax_period: Annotated[str, Query(description="Tax period, e.g. 2026-04.")],
    filing_frequency: GSTFilingFrequency = GSTFilingFrequency.MONTHLY,
    export_format: GSTExportFormat = GSTExportFormat.JSON,
) -> SuccessResponse[GSTR3BReport] | Response:
    """Generate GSTR-3B."""
    await _ensure_business_member(uow, business_id, current_user.id)
    report = await service.generate_gstr3b(
        GSTReportRequest(
            business_id=business_id,
            tax_period=tax_period,
            filing_frequency=filing_frequency,
        )
    )
    return _format_response(service, report, export_format, "GSTR-3B generated")


@router.get(
    "/itc",
    response_model=SuccessResponse[ITCReport],
    status_code=status.HTTP_200_OK,
    summary="Generate ITC report",
    description="Generates input tax credit report from posted source data.",
)
async def generate_itc(
    current_user: CurrentUser,
    uow: ComplianceUnitOfWorkDep,
    service: ComplianceServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    tax_period: Annotated[str, Query(description="Tax period, e.g. 2026-04.")],
    filing_frequency: GSTFilingFrequency = GSTFilingFrequency.MONTHLY,
    export_format: GSTExportFormat = GSTExportFormat.JSON,
) -> SuccessResponse[ITCReport] | Response:
    """Generate ITC report."""
    await _ensure_business_member(uow, business_id, current_user.id)
    report = await service.generate_itc_report(
        GSTReportRequest(
            business_id=business_id,
            tax_period=tax_period,
            filing_frequency=filing_frequency,
        )
    )
    return _format_response(service, report, export_format, "ITC report generated")


@router.get(
    "/hsn",
    response_model=SuccessResponse[list[HSNReportLine]],
    status_code=status.HTTP_200_OK,
    summary="Generate HSN summary",
    description="Generates HSN summary from posted source data.",
)
async def generate_hsn(
    current_user: CurrentUser,
    uow: ComplianceUnitOfWorkDep,
    service: ComplianceServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    tax_period: Annotated[str, Query(description="Tax period, e.g. 2026-04.")],
    filing_frequency: GSTFilingFrequency = GSTFilingFrequency.MONTHLY,
    export_format: GSTExportFormat = GSTExportFormat.JSON,
) -> SuccessResponse[list[HSNReportLine]] | Response:
    """Generate HSN summary."""
    await _ensure_business_member(uow, business_id, current_user.id)
    report = await service.generate_hsn_summary(
        GSTReportRequest(
            business_id=business_id,
            tax_period=tax_period,
            filing_frequency=filing_frequency,
        )
    )
    return _format_response(service, report, export_format, "HSN summary generated")


@router.get(
    "/audit",
    response_model=SuccessResponse[GSTAuditReportResponse],
    status_code=status.HTTP_200_OK,
    summary="Generate GST audit report",
    description="Audits posted source data for GST consistency issues.",
)
async def generate_audit(
    current_user: CurrentUser,
    uow: ComplianceUnitOfWorkDep,
    service: ComplianceServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    tax_period: Annotated[str, Query(description="Tax period, e.g. 2026-04.")],
    filing_frequency: GSTFilingFrequency = GSTFilingFrequency.MONTHLY,
    export_format: GSTExportFormat = GSTExportFormat.JSON,
) -> SuccessResponse[GSTAuditReportResponse] | Response:
    """Generate GST audit report."""
    await _ensure_business_member(uow, business_id, current_user.id)
    report = await service.generate_audit_report(
        GSTReportRequest(
            business_id=business_id,
            tax_period=tax_period,
            filing_frequency=filing_frequency,
        )
    )
    return _format_response(service, report, export_format, "GST audit generated")


def _validate_provenance_params(
    *,
    comparison_source: str | None,
    is_portal_verified: bool | None,
) -> None:
    """Validate client comparison provenance parameters."""
    if is_portal_verified:
        raise GSTComparisonInputValidationException(
            "Client input cannot assert or imply government portal verification."
        )
    if comparison_source is not None:
        clean_source = str(comparison_source).strip().lower()
        if clean_source in ("government_portal", "portal"):
            raise GSTComparisonInputValidationException(
                "Client input cannot select government_portal as comparison source "
                "without authorized server-side provider evidence."
            )
        if clean_source in ("mock", "sandbox", "testbed", "sandbox_gst_verifier"):
            raise GSTComparisonInputValidationException(
                "Testbed or mock sources cannot satisfy government portal "
                "verification or comparison provenance."
            )
        if clean_source not in ("unprovided", "user_supplied"):
            raise GSTComparisonInputValidationException(
                f"Unsupported comparison source: '{comparison_source}'."
            )


def _validate_numeric_comparison_params(
    *,
    outward_params: dict[str, Decimal | None],
    itc_params: dict[str, Decimal | None],
    gstr3b_tax_amount: Decimal | None,
    gstr3b_itc_amount: Decimal | None,
) -> None:
    """Validate non-negative and additive consistency of comparison inputs."""
    for param_name, param_val in {**outward_params, **itc_params}.items():
        if param_val is not None and param_val < Decimal("0.00"):
            raise GSTComparisonInputValidationException(
                f"Comparison parameter '{param_name}' cannot be negative: ₹{param_val}."
            )

    outward_components = [
        outward_params["gstr3b_cgst_amount"],
        outward_params["gstr3b_sgst_amount"],
        outward_params["gstr3b_igst_amount"],
        outward_params["gstr3b_utgst_amount"],
        outward_params["gstr3b_cess_amount"],
    ]
    if gstr3b_tax_amount is not None and any(
        x is not None for x in outward_components
    ):
        outward_comp_sum = sum(
            (x or Decimal("0.00") for x in outward_components), Decimal("0.00")
        )
        if outward_comp_sum != gstr3b_tax_amount:
            raise GSTComparisonInputValidationException(
                "Contradictory outward comparison input: tax amount "
                f"₹{gstr3b_tax_amount} does not match sum of individual "
                f"components ₹{outward_comp_sum}."
            )

    itc_components = [
        itc_params["gstr3b_itc_cgst_amount"],
        itc_params["gstr3b_itc_sgst_amount"],
        itc_params["gstr3b_itc_igst_amount"],
        itc_params["gstr3b_itc_utgst_amount"],
        itc_params["gstr3b_itc_cess_amount"],
    ]
    if gstr3b_itc_amount is not None and any(
        x is not None for x in itc_components
    ):
        itc_comp_sum = sum(
            (x or Decimal("0.00") for x in itc_components), Decimal("0.00")
        )
        if itc_comp_sum != gstr3b_itc_amount:
            raise GSTComparisonInputValidationException(
                "Contradictory ITC comparison input: ITC amount "
                f"₹{gstr3b_itc_amount} does not match sum of individual "
                f"components ₹{itc_comp_sum}."
            )


@router.get(
    "/reconciliation",
    response_model=SuccessResponse[GSTRReconciliationReport],
    status_code=status.HTTP_200_OK,
    summary="Generate GST returns reconciliation",
    description=(
        "Reconciles GSTR-1 outward liability vs GSTR-3B and inward books ITC"
        " under CBIC Rule 88C/88D."
    ),
)
async def generate_reconciliation(
    current_user: CurrentUser,
    uow: ComplianceUnitOfWorkDep,
    service: ComplianceServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    tax_period: Annotated[str, Query(description="Tax period, e.g. 2026-04.")],
    filing_frequency: GSTFilingFrequency = GSTFilingFrequency.MONTHLY,
    export_format: GSTExportFormat = GSTExportFormat.JSON,
    gstr3b_taxable_value: Annotated[
        Decimal | None,
        Query(description="GSTR-3B reported taxable turnover."),
    ] = None,
    gstr3b_tax_amount: Annotated[
        Decimal | None,
        Query(description="GSTR-3B reported tax liability."),
    ] = None,
    gstr3b_cgst_amount: Annotated[
        Decimal | None,
        Query(description="GSTR-3B reported CGST liability."),
    ] = None,
    gstr3b_sgst_amount: Annotated[
        Decimal | None,
        Query(description="GSTR-3B reported SGST liability."),
    ] = None,
    gstr3b_igst_amount: Annotated[
        Decimal | None,
        Query(description="GSTR-3B reported IGST liability."),
    ] = None,
    gstr3b_utgst_amount: Annotated[
        Decimal | None,
        Query(description="GSTR-3B reported UTGST liability."),
    ] = None,
    gstr3b_cess_amount: Annotated[
        Decimal | None,
        Query(description="GSTR-3B reported Cess liability."),
    ] = None,
    gstr3b_itc_taxable_value: Annotated[
        Decimal | None,
        Query(description="GSTR-3B reported inward taxable value."),
    ] = None,
    gstr3b_itc_amount: Annotated[
        Decimal | None,
        Query(description="GSTR-3B reported total ITC."),
    ] = None,
    gstr3b_itc_cgst_amount: Annotated[
        Decimal | None,
        Query(description="GSTR-3B reported CGST ITC."),
    ] = None,
    gstr3b_itc_sgst_amount: Annotated[
        Decimal | None,
        Query(description="GSTR-3B reported SGST ITC."),
    ] = None,
    gstr3b_itc_igst_amount: Annotated[
        Decimal | None,
        Query(description="GSTR-3B reported IGST ITC."),
    ] = None,
    gstr3b_itc_utgst_amount: Annotated[
        Decimal | None,
        Query(description="GSTR-3B reported UTGST ITC."),
    ] = None,
    gstr3b_itc_cess_amount: Annotated[
        Decimal | None,
        Query(description="GSTR-3B reported Cess ITC."),
    ] = None,
    comparison_source: Annotated[
        str | None,
        Query(
            description=(
                "Restricted provenance parameter: clients cannot assert"
                " government portal source without authorized server evidence."
            ),
        ),
    ] = None,
    is_portal_verified: Annotated[
        bool | None,
        Query(
            description=(
                "Restricted verification parameter: clients cannot assert"
                " government portal verification without authorized server evidence."
            ),
        ),
    ] = None,
) -> SuccessResponse[GSTRReconciliationReport] | Response:
    """Generate GST returns reconciliation."""
    await _ensure_business_member(uow, business_id, current_user.id)

    _validate_provenance_params(
        comparison_source=comparison_source,
        is_portal_verified=is_portal_verified,
    )

    outward_numeric_params = {
        "gstr3b_taxable_value": gstr3b_taxable_value,
        "gstr3b_tax_amount": gstr3b_tax_amount,
        "gstr3b_cgst_amount": gstr3b_cgst_amount,
        "gstr3b_sgst_amount": gstr3b_sgst_amount,
        "gstr3b_igst_amount": gstr3b_igst_amount,
        "gstr3b_utgst_amount": gstr3b_utgst_amount,
        "gstr3b_cess_amount": gstr3b_cess_amount,
    }
    itc_numeric_params = {
        "gstr3b_itc_taxable_value": gstr3b_itc_taxable_value,
        "gstr3b_itc_amount": gstr3b_itc_amount,
        "gstr3b_itc_cgst_amount": gstr3b_itc_cgst_amount,
        "gstr3b_itc_sgst_amount": gstr3b_itc_sgst_amount,
        "gstr3b_itc_igst_amount": gstr3b_itc_igst_amount,
        "gstr3b_itc_utgst_amount": gstr3b_itc_utgst_amount,
        "gstr3b_itc_cess_amount": gstr3b_itc_cess_amount,
    }
    _validate_numeric_comparison_params(
        outward_params=outward_numeric_params,
        itc_params=itc_numeric_params,
        gstr3b_tax_amount=gstr3b_tax_amount,
        gstr3b_itc_amount=gstr3b_itc_amount,
    )

    has_outward = any(
        x is not None
        for x in (
            gstr3b_taxable_value,
            gstr3b_tax_amount,
            gstr3b_cgst_amount,
            gstr3b_sgst_amount,
            gstr3b_igst_amount,
            gstr3b_utgst_amount,
            gstr3b_cess_amount,
        )
    )
    gstr3b_liability_override: GSTAmountSummary | None = None
    if has_outward:
        taxable = (
            gstr3b_taxable_value
            if gstr3b_taxable_value is not None
            else Decimal("0.00")
        )
        cgst = (
            gstr3b_cgst_amount
            if gstr3b_cgst_amount is not None
            else Decimal("0.00")
        )
        sgst = (
            gstr3b_sgst_amount
            if gstr3b_sgst_amount is not None
            else Decimal("0.00")
        )
        igst = (
            gstr3b_igst_amount
            if gstr3b_igst_amount is not None
            else Decimal("0.00")
        )
        utgst = (
            gstr3b_utgst_amount
            if gstr3b_utgst_amount is not None
            else Decimal("0.00")
        )
        cess = (
            gstr3b_cess_amount
            if gstr3b_cess_amount is not None
            else Decimal("0.00")
        )
        component_sum = cgst + sgst + igst + utgst + cess
        tax = gstr3b_tax_amount if gstr3b_tax_amount is not None else component_sum
        gstr3b_liability_override = GSTAmountSummary(
            taxable_value=taxable,
            cgst_amount=cgst,
            sgst_amount=sgst,
            igst_amount=igst,
            utgst_amount=utgst,
            cess_amount=cess,
            tax_amount=tax,
            total_amount=taxable + tax,
        )

    has_itc = any(
        x is not None
        for x in (
            gstr3b_itc_taxable_value,
            gstr3b_itc_amount,
            gstr3b_itc_cgst_amount,
            gstr3b_itc_sgst_amount,
            gstr3b_itc_igst_amount,
            gstr3b_itc_utgst_amount,
            gstr3b_itc_cess_amount,
        )
    )
    gstr3b_itc_override: GSTAmountSummary | None = None
    if has_itc:
        itc_taxable = (
            gstr3b_itc_taxable_value
            if gstr3b_itc_taxable_value is not None
            else Decimal("0.00")
        )
        itc_cgst = (
            gstr3b_itc_cgst_amount
            if gstr3b_itc_cgst_amount is not None
            else Decimal("0.00")
        )
        itc_sgst = (
            gstr3b_itc_sgst_amount
            if gstr3b_itc_sgst_amount is not None
            else Decimal("0.00")
        )
        itc_igst = (
            gstr3b_itc_igst_amount
            if gstr3b_itc_igst_amount is not None
            else Decimal("0.00")
        )
        itc_utgst = (
            gstr3b_itc_utgst_amount
            if gstr3b_itc_utgst_amount is not None
            else Decimal("0.00")
        )
        itc_cess = (
            gstr3b_itc_cess_amount
            if gstr3b_itc_cess_amount is not None
            else Decimal("0.00")
        )
        itc_component_sum = itc_cgst + itc_sgst + itc_igst + itc_utgst + itc_cess
        itc_tax = (
            gstr3b_itc_amount
            if gstr3b_itc_amount is not None
            else itc_component_sum
        )
        gstr3b_itc_override = GSTAmountSummary(
            taxable_value=itc_taxable,
            cgst_amount=itc_cgst,
            sgst_amount=itc_sgst,
            igst_amount=itc_igst,
            utgst_amount=itc_utgst,
            cess_amount=itc_cess,
            tax_amount=itc_tax,
            total_amount=itc_taxable + itc_tax,
        )

    report = await service.generate_reconciliation(
        GSTReportRequest(
            business_id=business_id,
            tax_period=tax_period,
            filing_frequency=filing_frequency,
        ),
        gstr3b_liability_override=gstr3b_liability_override,
        gstr3b_itc_override=gstr3b_itc_override,
        comparison_source=comparison_source,
        is_portal_verified=bool(is_portal_verified),
    )
    return _format_response(
        service,
        report,
        export_format,
        "GST reconciliation generated",
    )



def _format_response(
    service: GSTComplianceService,
    report: Any,
    export_format: GSTExportFormat,
    message: str,
) -> SuccessResponse[Any] | Response:
    """Return JSON success response or CSV response."""
    if export_format == GSTExportFormat.CSV:
        return Response(
            content=service.export_csv(report),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=gst-report.csv"},
        )
    return SuccessResponse(success=True, message=message, data=report)


async def _ensure_business_member(
    uow: Any,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Raise when current user is not a business member."""
    async with uow:
        if not await uow.business_memberships.is_member(
            business_id=business_id,
            user_id=user_id,
        ):
            raise BusinessNotMemberException(
                "User is not a member of the business",
                details={"business_id": str(business_id), "user_id": str(user_id)},
            )
